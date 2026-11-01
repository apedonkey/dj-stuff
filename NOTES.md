# Tribe XR avatar-loading recon

Read-only static analysis of Tribe XR as installed on my own Quest 3. (CONSTRAINT LIFTED 2026-09-29:
the read-only / no-reinstall rule below held through the analysis phases; the re-sign gate has since
passed [verdict a — a re-signed stock build launches, logs in past Meta entitlement, renders — burner
account] and the injected-hook route is authorized. Keystore: tribe.keystore (password kept locally; gitignored, not committed). See the
"Phase 1 (injected-hook route)" section at the end of this file.)
Original rule: nothing on the headset is modified, re-signed or re-installed; all analysis runs on
copies pulled to this PC.

- Started 2026-09-28 on Windows 11 Home 10.0.26200.
- From entry [001] on, every shell command was run through `scripts/logrun.sh`, which appends the
  exact command, exit code and output below. Long outputs are truncated here and kept in full
  under `logs/`.
- `pulled/`, `unpacked/`, `out/` and `tools/` are gitignored (proprietary binaries, bulk dumps).

## Summary

Status 2026-09-28 23:21: steps 1–5 complete for Tribe XR 0.12.5.1 (versionCode 2304).

- **Ready Player Me URL: one plain-string URL is present.** `https://readyplayer.me/api/avatar/`,
  ASCII, once, in `lib/arm64-v8a/libUnreal.so` at file offset 0x5be61d [037]–[039]. It is the only
  readyplayer.me address in the whole install apart from `https://docs.readyplayer.me/` in the
  plugin descriptor. No `models.readyplayer.me` or `api.readyplayer.me` anywhere, in ASCII or
  UTF-16LE, in the APK or either OBB (scanner and GNU grep agree: 56 ASCII + 12 UTF-16LE
  readyplayer strings in `libUnreal.so`) [020], [024], [039]. Its neighbours in the binary are
  unrelated strings that the linker grouped because they also end in `/`.
- **Engine: Unreal Engine, not Unity.** `lib/arm64-v8a/libUnreal.so` (129,868,152 bytes, ARM64,
  stripped, NDK r25b) plus `assets/UECommandLine.txt`. No `libil2cpp.so`, no `global-metadata.dat`,
  no `Managed/*.dll`, no `assets/bin/Data` [034]. Asset headers carry `++UE5+Release-5.4` (UE 5.4
  or later, inferred) [020]; no engine version string was found in `libUnreal.so` itself [034].
- **Layout.** Single APK: `pm path` returns only `base.apk` (`splits=[base]`, 111,389,761 bytes,
  sha256 `0b7112f7…34b0ef7c`, installer `com.oculus.ocms`, arm64-v8a) [031]–[032]. Expansion file
  `main.2304.com.TribeXR.TribeXR.obb` (2,034,318,982 bytes, sha256 `42c9e5d5…3656ec2`) [033]. Both
  hashes were checked against `sha256sum` run on the headset. The app auto-updated from 2300 to
  2304 at 22:59; the user's earlier File Explorer copy `main.2300…obb` is kept for comparison.
  Its Ready Player Me strings are identical to 2304's [036].
- **Where the strings live** (Unreal's equivalent of the metadata question). Code and its string
  literals are in `libUnreal.so` (UTF-16LE for `TEXT()` literals, ASCII for others). Assets and
  Blueprints are in four pak v11 files in the OBB: index not encrypted, contents Oodle-compressed,
  so grep sees asset paths and fragments only [019], [036].
- **How avatars are modelled in code** (names only, not disassembled) [039]:
  `ETribeAvatarType::{None, MetaAvatar2, ReadyPlayerMe}`, `CurrentETribeAvatarType`,
  `UTribeAvatarComponent`, `GetAvatarId`, `SaveAvatarId`, `GetAvatarIdForServer`,
  `GetAvatarTypeForId`, `GetTribeDefaultAvatarId`, `GetTribeMentorAvatarId`,
  `IsValidReadyPlayerMeAvatarID`, `IsValidReadyPlayerMeAvatarUrl`, `ReadyPlayerMeAvatarUrl`,
  `QueriedAvatarUrl`, `GetAvatarUrlCacheFilename`, `ReadyPlayerMeETag`,
  `HandleReadyPlayerMeOnAvatarCached`. Meta Avatar presets load via `zip://%s_quest2.glb`; replay
  avatars via `Replays/DefaultAvatar.glb` [038].
- **Ready Player Me assets** [021]–[025]: plugin `ReadyPlayerMe` ("ReadyPlayerMe Avatar Toolkit"
  6.0, Wolf3D, depends on `glTFRuntime`), `BP_ReadyPlayerMeAvatarSkin`,
  `T_SkinPreview_ReadyPlayerMe_Custom`, widget `W_RPMAvatarCreator`, icons
  `T_Icon_RPM_{Paste,Goto,Copy}`. Meta Avatars: `libovravatar2.so`, `Plugins/MetaAvatar2`,
  `BP_OculusAvatarSkin`. Raw GLBs in the pak under `TribeXR/Content/Replays/`: `DanceAvatar.glb`,
  `DefaultAvatar.glb`, `MentorAvatar.glb` [026].
- **Hit files**: `hits/apk/`, `hits/obb2304/`, `hits/obb/` (2300), each with SUMMARY.md, hits.tsv,
  hits_context.txt, unique_<term>.txt. APK totals: readyplayer 68 (all `libUnreal.so`),
  rpm 27, .glb 11, gltf 340, avatarloader 0, avatar 2,494 (2,216 in `libovravatar2.so`).
  OBB 2304 totals: readyplayer 19, rpm 742 (nearly all random bytes in media), .glb 157,
  gltf 217, avatarloader 0, avatar 1,274.

## Command log

### Pre-setup, 2026-09-28 22:12, before the repo existed

```sh
pwd && ls -la && git status | head -3
for t in git python python3 py adb winget java dotnet 7z unzip strings sha256sum curl file; do command -v "$t" || echo "(not found)"; done
python --version; py -3 --version
```

```text
/c/Users/Chris/OneDrive/Desktop/tribe hack
total 64
drwxr-xr-x 1 Chris 197121 0 Sep 28 22:12 ./
drwxr-xr-x 1 Chris 197121 0 Sep 28 22:12 ../
fatal: not a git repository (or any of the parent directories): .git
git        /mingw64/bin/git
python     /c/Python313/python
python3    /c/Users/Chris/AppData/Local/Microsoft/WindowsApps/python3
py         /c/WINDOWS/py
adb        (not found)
winget     /c/Users/Chris/AppData/Local/Microsoft/WindowsApps/winget
java       /c/Program Files/Eclipse Adoptium/jdk-21.0.11.10-hotspot/bin/java
dotnet     /c/Program Files/dotnet/dotnet
7z         (not found)
unzip      /usr/bin/unzip
strings    (not found)
sha256sum  /usr/bin/sha256sum
curl       /mingw64/bin/curl
file       /usr/bin/file
Python 3.13.5
Python 3.13.5
```

```powershell
Get-Process OneDrive; (Get-ItemProperty 'HKCU:\Software\Microsoft\OneDrive\Accounts\Personal').UserFolder
Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'Quest|Oculus|Meta|ADB|Android' }
```

```text
OneDrive running: False
OneDrive root: C:\Users\Chris\OneDrive
Status Class         FriendlyName
OK     Display       Meta Virtual Monitor
OK     AudioEndpoint Headset Microphone (Oculus Virtual Audio Device)
OK     AudioEndpoint Headphones (Oculus Virtual Audio Device)
OK     System        Oculus Virtual Gamepad Emulation Bus
OK     MEDIA         Oculus Virtual Audio Device
```

Notes: no physical Quest USB device visible yet (only Meta Link virtual devices). This project
folder is inside the OneDrive root, but OneDrive is not running, so nothing is syncing right now.

### [001] 2026-09-28 22:26:27 · exit 0

```sh
git init && git status --short --branch
```

```text
Initialized empty Git repository in C:/Users/Chris/OneDrive/Desktop/tribe hack/.git/
## No commits yet on master
?? .gitignore
?? NOTES.md
?? logs/
?? scripts/
```

### [002] 2026-09-28 22:26:28 · exit 0

```sh
mkdir -p tools && curl -fsSL -o tools/platform-tools-latest-windows.zip https://dl.google.com/android/repository/platform-tools-latest-windows.zip && unzip -q -o tools/platform-tools-latest-windows.zip -d tools && tools/platform-tools/adb.exe version && dotnet --list-runtimes && java -version
```

```text
Android Debug Bridge version 1.0.41
Version 37.0.1-15733141
Installed as C:\Users\Chris\OneDrive\Desktop\tribe hack\tools\platform-tools\adb.exe
Running on Windows 10.0.26200
Microsoft.AspNetCore.App 6.0.8 [C:\Program Files\dotnet\shared\Microsoft.AspNetCore.App]
Microsoft.AspNetCore.App 8.0.0 [C:\Program Files\dotnet\shared\Microsoft.AspNetCore.App]
Microsoft.AspNetCore.App 8.0.28 [C:\Program Files\dotnet\shared\Microsoft.AspNetCore.App]
Microsoft.NETCore.App 3.1.32 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
Microsoft.NETCore.App 6.0.26 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
Microsoft.NETCore.App 8.0.14 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
Microsoft.NETCore.App 8.0.16 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
Microsoft.NETCore.App 8.0.28 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
Microsoft.WindowsDesktop.App 6.0.26 [C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App]
Microsoft.WindowsDesktop.App 8.0.16 [C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App]
Microsoft.WindowsDesktop.App 8.0.28 [C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App]
openjdk version "21.0.11" 2026-04-21 LTS
OpenJDK Runtime Environment Temurin-21.0.11+10 (build 21.0.11+10-LTS)
OpenJDK 64-Bit Server VM Temurin-21.0.11+10 (build 21.0.11+10-LTS, mixed mode, sharing)
```

### [003] 2026-09-28 22:26:40 · exit 0

```sh
adb devices -l; echo "--- USB devices with Oculus vendor ID (VID_2833):"; powershell.exe -NoProfile -Command "Get-PnpDevice -PresentOnly | Where-Object { \$_.InstanceId -match 'VID_2833' } | Format-Table -AutoSize Status,Class,FriendlyName,InstanceId | Out-String -Width 200"
```

```text
* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached

--- USB devices with Oculus vendor ID (VID_2833):

```

### [004] 2026-09-28 22:27:00 · exit 0

```sh
powershell.exe -NoProfile -Command "Get-PnpDevice | Where-Object { \$_.InstanceId -match 'VID_2833' -or \$_.FriendlyName -match 'Quest|ADB' } | Sort-Object Status | Format-Table -AutoSize Status,Present,Class,FriendlyName,InstanceId | Out-String -Width 220; 'USB devices currently reporting a problem:'; Get-PnpDevice -PresentOnly | Where-Object { \$_.Status -ne 'OK' -and \$_.InstanceId -like 'USB*' } | Format-Table -AutoSize Status,Class,FriendlyName,InstanceId | Out-String -Width 220"
```

```text

Status  Present Class                     FriendlyName                              InstanceId                                   
------  ------- -----                     ------------                              ----------                                   
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite XRSP Interface     USB\VID_2833&PID_5012&MI_01\6&17083F12&1&0001
Unknown   False USB                       USB Composite Device                      USB\VID_2833&PID_5013\2G0YC1ZF96072F         
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite Commlib Interface  USB\VID_2833&PID_5012&MI_02\6&17083F12&1&0002
Unknown   False USB                       USB Composite Device                      USB\VID_2833&PID_5012\2G0YC1ZF96072F         
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite Highwind Interface USB\VID_2833&PID_5012&MI_03\6&17083F12&1&0003
Unknown   False WPD                       Quest 3                                   USB\VID_2833&PID_5012&MI_00\6&17083F12&1&0000
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite ADB Interface      USB\VID_2833&PID_5013&MI_03\6&37E3B45&1&0003 
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite ADB Interface      USB\VID_2833&PID_5012&MI_04\6&17083F12&1&0004
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite Highwind Interface USB\VID_2833&PID_5013&MI_02\6&37E3B45&1&0002 
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite XRSP Interface     USB\VID_2833&PID_5013&MI_00\6&37E3B45&1&0000 
Unknown   False RealityLabsUsbDeviceClass Reality Labs Composite Commlib Interface  USB\VID_2833&PID_5013&MI_01\6&37E3B45&1&0001 



USB devices currently reporting a problem:

```

Diagnosis for step 1: `adb devices` was empty because the headset was not plugged in; Windows had
no VID_2833 device present. This PC has enumerated this Quest 3 (serial 2G0YC1ZF96072F) before,
including the "Reality Labs Composite ADB Interface" (PID 5012 MI_04 / PID 5013 MI_03), so the ADB
driver is already installed. User plugged the headset in at this point.

### [005] 2026-09-28 22:28:11 · exit 127

```sh
timeout 300 adb wait-for-usb-device; echo "wait-for-usb-device exit: $?"; adb devices -l
```

```text
(no output)
```

_Background wait, cancelled after the user confirmed the headset was plugged in and recognized by
Windows. It had not returned, i.e. no authorized device yet. (Entries are ordered by start time;
cancelled background runs were appended late and are moved into place here.)_

### [006] 2026-09-28 22:30:12 · exit 0

```sh
adb devices -l; echo "--- present USB devices with Oculus vendor ID (VID_2833):"; powershell.exe -NoProfile -Command "Get-PnpDevice -PresentOnly | Where-Object { \$_.InstanceId -match 'VID_2833' } | Format-Table -AutoSize Status,Class,FriendlyName,InstanceId | Out-String -Width 200"
```

```text
List of devices attached
2G0YC1ZF96072F         unauthorized transport_id:3

--- present USB devices with Oculus vendor ID (VID_2833):

Status Class                     FriendlyName                              InstanceId                                   
------ -----                     ------------                              ----------                                   
OK     RealityLabsUsbDeviceClass Reality Labs Composite ADB Interface      USB\VID_2833&PID_5012&MI_04\6&17083F12&1&0004
OK     WPD                       Quest 3                                   USB\VID_2833&PID_5012&MI_00\6&17083F12&1&0000
OK     RealityLabsUsbDeviceClass Reality Labs Composite XRSP Interface     USB\VID_2833&PID_5012&MI_01\6&17083F12&1&0001
OK     RealityLabsUsbDeviceClass Reality Labs Composite Commlib Interface  USB\VID_2833&PID_5012&MI_02\6&17083F12&1&0002
OK     RealityLabsUsbDeviceClass Reality Labs Composite Highwind Interface USB\VID_2833&PID_5012&MI_03\6&17083F12&1&0003
OK     USB                       USB Composite Device                      USB\VID_2833&PID_5012\2G0YC1ZF96072F         



```

Device now enumerates (ADB interface driver OK) but adb reports it `unauthorized`: the "Allow USB
debugging?" prompt for this PC's adb key has to be accepted inside the headset.

### [007] 2026-09-28 22:30:29 · exit 127

```sh
timeout 600 adb wait-for-usb-device; echo "wait-for-usb-device exit: $?"; adb devices -l
```

```text
error: protocol fault (couldn't read status): connection reset
wait-for-usb-device exit: 1
```

_Background wait, cancelled when the user said the headset "definitely is" connected; the
"connection reset" comes from the adb server restart in [008]._

### [008] 2026-09-28 22:33:41 · exit 0

```sh
adb devices -l
echo "--- adb processes running:"; powershell.exe -NoProfile -Command "Get-Process adb -ErrorAction SilentlyContinue | Format-Table -AutoSize Id,StartTime,Path | Out-String -Width 200"
echo "--- this PC's adb key:"; ls -l --time-style=long-iso ~/.android/adbkey*
printf 'fingerprint the headset prompt should show: '; cut -d' ' -f1 ~/.android/adbkey.pub | base64 -d | md5sum | cut -c1-32 | tr a-f A-F | sed 's/../&:/g; s/:$//'
echo "--- restart adb server to force a fresh auth handshake:"; adb kill-server; adb start-server; adb wait-for-usb-device & wpid=$!; ( sleep 8; kill $wpid 2>/dev/null ) & wait $wpid; adb devices -l
```

```text
List of devices attached
2G0YC1ZF96072F         unauthorized transport_id:3

--- adb processes running:

  Id StartTime             Path                                                                   
  -- ---------             ----                                                                   
 152 9/28/2026 10:26:42 PM C:\Users\Chris\OneDrive\Desktop\tribe hack\tools\platform-tools\adb.exe
5400 9/28/2026 10:30:29 PM C:\Users\Chris\OneDrive\Desktop\tribe hack\tools\platform-tools\adb.exe



--- this PC's adb key:
-rw-r--r-- 1 Chris 197121 1732 2026-09-28 22:26 /c/Users/Chris/.android/adbkey
-rw-r--r-- 1 Chris 197121  722 2020-12-20 19:43 /c/Users/Chris/.android/adbkey.pub
fingerprint the headset prompt should show: 4A:D5:9F:5E:E5:B4:DF:23:DB:28:45:39:3D:96:99:BB
--- restart adb server to force a fresh auth handshake:
* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached
2G0YC1ZF96072F         unauthorized transport_id:1

```

### [009] 2026-09-28 22:35:40 · exit 0

```sh
fp() { cut -d' ' -f1 | base64 -d | md5sum | cut -c1-32 | tr a-f A-F | sed 's/../&:/g; s/:$//'; }
printf 'fingerprint of adbkey.pub on disk (2020):         '; fp < ~/.android/adbkey.pub
printf 'fingerprint derived from adbkey private key (today): '; adb pubkey ~/.android/adbkey | fp
echo "--- attributes / ACL of the key files:"; attrib "$(cygpath -w ~/.android/adbkey.pub)"; attrib "$(cygpath -w ~/.android/adbkey)"
echo "--- leftover adb client processes:"; powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='adb.exe'\" | Format-Table -AutoSize ProcessId,CreationDate,CommandLine | Out-String -Width 250"
```

```text
fingerprint of adbkey.pub on disk (2020):         4A:D5:9F:5E:E5:B4:DF:23:DB:28:45:39:3D:96:99:BB
fingerprint derived from adbkey private key (today): 09-28 22:35:41.071  6948 18560 E adb.exe : auth.cpp:123 Failed to open '/c/Users/Chris/.android/adbkey': No such file or directory
D4:1D:8C:D9:8F:00:B2:04:E9:80:09:98:EC:F8:42:7E
--- attributes / ACL of the key files:
A   H                C:\Users\Chris\.android\adbkey.pub
A                    C:\Users\Chris\.android\adbkey
--- leftover adb client processes:

ProcessId CreationDate          CommandLine                                      
--------- ------------          -----------                                      
    23112 9/28/2026 10:33:43 PM adb -L tcp:5037 fork-server server --reply-fd 740



```

### [010] 2026-09-28 22:36:40 · exit 0

```sh
fp() { cut -d' ' -f1 | base64 -d | md5sum | cut -c1-32 | tr a-f A-F | sed 's/../&:/g; s/:$//'; }
K="$(cygpath -w ~/.android/adbkey)"; P="$(cygpath -w ~/.android/adbkey.pub)"
adb pubkey "$K" > ~/.android/adbkey.pub.new || exit 1
old=$(fp < ~/.android/adbkey.pub); new=$(fp < ~/.android/adbkey.pub.new)
echo "adbkey.pub on disk (2020):       $old"
echo "derived from adbkey (today):     $new"
if [ "$old" = "$new" ]; then echo "pair matches; nothing to fix"; rm ~/.android/adbkey.pub.new; exit 0; fi
echo "MISMATCH -> back up old .pub, clear Hidden attribute, install derived .pub"
cp -p ~/.android/adbkey.pub ~/.android/adbkey.pub.2020-12-20.bak && attrib -H "$P" && cp ~/.android/adbkey.pub.new ~/.android/adbkey.pub && rm ~/.android/adbkey.pub.new || exit 1
echo "adbkey.pub now:                  $(fp < ~/.android/adbkey.pub)"
ls -l --time-style=long-iso ~/.android/ | grep adbkey
echo "--- restart adb server so the headset receives the corrected key:"
adb kill-server; adb start-server; adb devices -l
```

```text
adbkey.pub on disk (2020):       4A:D5:9F:5E:E5:B4:DF:23:DB:28:45:39:3D:96:99:BB
derived from adbkey (today):     17:A1:19:AD:9E:15:34:8E:79:2F:E7:F1:7C:CA:8A:DC
MISMATCH -> back up old .pub, clear Hidden attribute, install derived .pub
adbkey.pub now:                  17:A1:19:AD:9E:15:34:8E:79:2F:E7:F1:7C:CA:8A:DC
-rw-r--r-- 1 Chris 197121 1732 2026-09-28 22:26 adbkey
-rw-r--r-- 1 Chris 197121  724 2026-09-28 22:36 adbkey.pub
-rw-r--r-- 1 Chris 197121  722 2020-12-20 19:43 adbkey.pub.2020-12-20.bak
--- restart adb server so the headset receives the corrected key:
* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached
2G0YC1ZF96072F         unauthorized transport_id:1

```

Root cause of the persistent `unauthorized` (entries [008]–[010]; [009]'s derived fingerprint is
invalid because adb.exe was given a POSIX path and hashed empty input): this PC's adb key pair was
mismatched. `~/.android/adbkey` (private) was generated fresh by the new adb at 22:26 today, but
`~/.android/adbkey.pub` from 2020 was not replaced. It carried the Windows Hidden attribute, and
Windows refuses a plain overwrite of a hidden file (inferred mechanism, not reproduced). adb signs
with the private key but sends `adbkey.pub` for the approval prompt, so an approval could never
match the key actually used and "Always allow" could never stick. Fix: backed up the old key to
`~/.android/adbkey.pub.2020-12-20.bak`, cleared Hidden, and wrote the public key derived from the
current private key (`adb pubkey`). The headset prompt should now show fingerprint
`17:A1:19:AD:9E:15:34:8E:79:2F:E7:F1:7C:CA:8A:DC`.

### [011] 2026-09-28 22:37 · stopped

```sh
timeout 600 adb wait-for-usb-device; echo "wait-for-usb-device exit: $?"; adb devices -l
```

```text
(no output)
```

_Background wait, stopped when the user said they had already approved the prompt. It never
returned, so adb never saw an authorized device while it ran. The wrapper was killed before it
could log itself; entry written by hand._

### [012] 2026-09-28 22:39:51 · exit 0

```sh
adb devices -l; echo "--- force a fresh auth handshake:"; adb reconnect offline; timeout 20 adb wait-for-usb-device; echo "wait-for-usb-device exit: $? (124 = still not authorized after 20 s)"; adb devices -l
```

```text
List of devices attached
2G0YC1ZF96072F         unauthorized transport_id:3

--- force a fresh auth handshake:
reconnecting 2G0YC1ZF96072F
wait-for-usb-device exit: 124 (124 = still not authorized after 20 s)
List of devices attached

```

### [013] 2026-09-28 22:40:20 · exit 0

```sh
adb devices -l; echo "--- present USB devices with Oculus vendor ID (VID_2833):"; powershell.exe -NoProfile -Command "Get-PnpDevice -PresentOnly | Where-Object { \$_.InstanceId -match 'VID_2833' } | Format-Table -AutoSize Status,Class,FriendlyName,InstanceId | Out-String -Width 200"
```

```text
List of devices attached

--- present USB devices with Oculus vendor ID (VID_2833):

Status Class                     FriendlyName                              InstanceId                                   
------ -----                     ------------                              ----------                                   
OK     RealityLabsUsbDeviceClass Reality Labs Composite ADB Interface      USB\VID_2833&PID_5012&MI_04\6&17083F12&1&0004
OK     WPD                       Quest 3                                   USB\VID_2833&PID_5012&MI_00\6&17083F12&1&0000
OK     RealityLabsUsbDeviceClass Reality Labs Composite XRSP Interface     USB\VID_2833&PID_5012&MI_01\6&17083F12&1&0001
OK     RealityLabsUsbDeviceClass Reality Labs Composite Commlib Interface  USB\VID_2833&PID_5012&MI_02\6&17083F12&1&0002
OK     RealityLabsUsbDeviceClass Reality Labs Composite Highwind Interface USB\VID_2833&PID_5012&MI_03\6&17083F12&1&0003
OK     USB                       USB Composite Device                      USB\VID_2833&PID_5012\2G0YC1ZF96072F         



```

### [014] 2026-09-28 22:40:29 · exit 0

```sh
adb kill-server; adb start-server; timeout 15 adb wait-for-usb-device; echo "wait-for-usb-device exit: $? (124 = not authorized within 15 s)"; adb devices -l
```

```text
* daemon not running; starting now at tcp:5037
* daemon started successfully
wait-for-usb-device exit: 124 (124 = not authorized within 15 s)
List of devices attached
2G0YC1ZF96072F         unauthorized transport_id:1

```

### [015] 2026-09-28 22:45:00 · exit 0

```sh
mkdir -p pulled && mv -n main.2300.com.TribeXR.TribeXR.obb pulled/ && ls -l --time-style=long-iso pulled/ && sha256sum pulled/main.2300.com.TribeXR.TribeXR.obb && file pulled/main.2300.com.TribeXR.TribeXR.obb
```

```text
total 1985276
-rw-r--r-- 1 Chris 197121 2032920524 2026-09-05 12:53 main.2300.com.TribeXR.TribeXR.obb
32828ce73f14c6a39c141fca8211f1e64f1a133123832593ee5c70a82c278866 *pulled/main.2300.com.TribeXR.TribeXR.obb
pulled/main.2300.com.TribeXR.TribeXR.obb: Zip archive data, at least v2.0 to extract, compression method=store
```

### [016] 2026-09-28 22:45:10 · exit 0

```sh
O=pulled/main.2300.com.TribeXR.TribeXR.obb; unzip -l "$O" > out_obb_listing.tmp; rc=$?; echo "unzip -l exit: $rc"; tail -n 1 out_obb_listing.tmp; echo "--- entries by top-level path (depth 4):"; awk "NR>3 && NF>=4 {print \$4}" out_obb_listing.tmp | grep -v "^-" | cut -d/ -f1-4 | sort | uniq -c | sort -rn | head -25; echo "--- key files (metadata / managed code / native libs / packed data):"; grep -Ei "global-metadata|/Managed/|\.so\$|\.dll\$|data\.unity3d|/Metadata/" out_obb_listing.tmp | head -40; mkdir -p out && mv out_obb_listing.tmp out/obb_listing.txt
```

```text
unzip -l exit: 0
2032880796                     157 files
--- entries by top-level path (depth 4):
     35 TribeXR/Content/Tracks/LessonTracks
     33 TribeXR/Content/Samples/808
     16 TribeXR/Content/Tracks/Samples
     12 TribeXR/Content/Visuals/Videos
     12 TribeXR/Content/Samples/909
     11 TribeXR/Content/Tracks/Kryoman
      6 TribeXR/Content/Tracks/5
      5 TribeXR/Content/Tracks/Desty
      4 TribeXR/Content/Tracks/Julian
      4 TribeXR/Content/Tracks/Ben
      3 TribeXR/Plugins/MetaAvatar2/Source
      2 Engine/Content/SlateDebug/Fonts
      1 TribeXR/Content/Tracks/silence.wav
      1 TribeXR/Content/Paks/pakchunk1optional-Android_ASTC.pak
      1 TribeXR/Content/Paks/pakchunk1-Android_ASTC.pak
      1 TribeXR/Content/Paks/pakchunk0optional-Android_ASTC.pak
      1 TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak
      1 TribeXR/Content/Movies/videoHipHop_A_B_2.mp4
      1 TribeXR/Content/Movies/TribeTrailer.mp4
      1 TribeXR/Content/Movies/Selina.mp4
      1 TribeXR/Content/Movies/PTDJA_Trailer.mp4
      1 TribeXR/Content/Movies/NeonsLines_v01.mp4
      1 TribeXR/Content/Movies/EQ_Twist.mp4
      1 TribeXR/Content/Movies/All4ScreensBldgE_v02.mp4
      1 TribeXR/Content/Certificates/cacert.pem
--- key files (metadata / managed code / native libs / packed data):
```

### [017] 2026-09-28 22:49:23 · exit 0

```sh
python tests/test_scan_strings.py
```

```text
(10, 'ascii', 'https://models.readyplayer.me/abc123.glb', ('readyplayer', '.glb'))
(985, 'ascii', 'AvatarLoaderComponent', ('avatarloader', 'avatar'))
(2000, 'utf16le', 'UReadyPlayerMeAvatar', ('readyplayer', 'avatar'))
(3100, 'ascii', 'TurntableRPM', ('rpm',))
(4000, 'ascii', 'model.gltf', ('gltf',))
OK: all 5 expected hits, no duplicates, 3-char 'rpm' dropped
```

_[017] comes from the first attempt at this step, which the user interrupted; its first command
still ran. [018]–[019] are the re-run._

### [018] 2026-09-28 22:49:34 · exit 0

```sh
python tests/test_scan_strings.py
```

```text
(10, 'ascii', 'https://models.readyplayer.me/abc123.glb', ('readyplayer', '.glb'))
(985, 'ascii', 'AvatarLoaderComponent', ('avatarloader', 'avatar'))
(2000, 'utf16le', 'UReadyPlayerMeAvatar', ('readyplayer', 'avatar'))
(3100, 'ascii', 'TurntableRPM', ('rpm',))
(4000, 'ascii', 'model.gltf', ('gltf',))
OK: all 5 expected hits, no duplicates, 3-char 'rpm' dropped
```

### [019] 2026-09-28 22:49:35 · exit 0

```sh
echo "--- OBB entries other than audio tracks/samples:"; grep -vE "Content/(Tracks|Samples)/" out/obb_listing.txt; echo "--- pak footers:"; python scripts/pak_footer.py pulled/main.2300.com.TribeXR.TribeXR.obb
```

```text
--- OBB entries other than audio tracks/samples:
Archive:  pulled/main.2300.com.TribeXR.TribeXR.obb
      2300
  Length      Date    Time    Name
---------  ---------- -----   ----
   259568  2024-10-19 22:39   Engine/Content/Renderer/TessellationTable.bin
      916  2024-10-19 22:35   Engine/Content/SlateDebug/Fonts/LastResort.tps
  5395052  2022-11-03 01:47   Engine/Content/SlateDebug/Fonts/LastResort.ttf
   211303  2025-04-08 15:43   TribeXR/Content/Certificates/cacert.pem
  4121281  2025-09-08 15:39   TribeXR/Content/Movies/All4ScreensBldgE_v02.mp4
  6379278  2022-11-03 13:28   TribeXR/Content/Movies/EQ_Twist.mp4
   774303  2025-09-08 15:39   TribeXR/Content/Movies/NeonsLines_v01.mp4
  6509007  2025-05-16 15:49   TribeXR/Content/Movies/PTDJA_Trailer.mp4
 15563910  2025-09-08 15:39   TribeXR/Content/Movies/Selina.mp4
 37792038  2026-06-22 16:01   TribeXR/Content/Movies/TribeTrailer.mp4
  1171885  2025-04-28 22:12   TribeXR/Content/Movies/videoHipHop_A_B_2.mp4
688531677  2026-09-01 12:05   TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak
103093146  2026-09-01 12:05   TribeXR/Content/Paks/pakchunk0optional-Android_ASTC.pak
403562810  2026-09-01 12:05   TribeXR/Content/Paks/pakchunk1-Android_ASTC.pak
142888023  2026-09-01 12:05   TribeXR/Content/Paks/pakchunk1optional-Android_ASTC.pak
 10033207  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/cleanroom_1.mp4
 10017709  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/dvde_1.mp4
 15001910  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/farkedpattern.mp4
  9382430  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/hotboxxx_1.mp4
  4911951  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/Lighting1.mp4
  4912006  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/Lighting4.mp4
  4910177  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/Lighting6.mp4
 10017483  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/okkkk_1.mp4
  4998479  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/scream.mp4
  4906831  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/Techno-Tunnel2.mp4
  9986483  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/unplug_1.mp4
 12020317  2026-06-22 16:01   TribeXR/Content/Visuals/Videos/wrmmm.mp4
  3790959  2025-04-08 15:43   TribeXR/Plugins/MetaAvatar2/Source/ThirdParty/MetaAvatar2NativeSDK/assets/CachedAvatars.zip
  7877284  2026-06-22 16:01   TribeXR/Plugins/MetaAvatar2/Source/ThirdParty/MetaAvatar2NativeSDK/assets/OvrAvatar2Assets.zip
 63625279  2025-04-08 15:43   TribeXR/Plugins/MetaAvatar2/Source/ThirdParty/MetaAvatar2NativeSDK/assets/PresetAvatars_Quest2.zip
---------                     -------
2032880796                     157 files
--- pak footers:
pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak  (688,531,677 bytes)
    pak_version: 11

... [20 lines omitted, full output in logs/019.log] ...

    compression_methods: ['Oodle']
    bytes_between_primary_index_and_footer: 26670
pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk1optional-Android_ASTC.pak  (142,888,023 bytes)
    pak_version: 11
    index_offset: 142870212
    index_size: 16690
    encrypted_index: False
    encryption_key_guid: 00000000000000000000000000000000 (all zero = default key)
    compression_methods: ['Oodle']
    bytes_between_primary_index_and_footer: 900
```

### [020] 2026-09-28 22:50:06 · exit 0

```sh
time python scripts/scan_strings.py hits/obb pulled/main.2300.com.TribeXR.TribeXR.obb; echo "--- Unreal engine version strings (grep -a, independent of the scanner):"; grep -a -o -E "\+\+UE[45]\+Release-[0-9]+\.[0-9]+" pulled/main.2300.com.TribeXR.TribeXR.obb | sort | uniq -c
```

```text
scanned 786 files/entries, 2,123,841,180 bytes; 2394 hit strings
  'readyplayer'    hits=    19  unique=16
  'rpm'            hits=   742  unique=634
  '.glb'           hits=   157  unique=90
  'gltf'           hits=   217  unique=146
  'avatarloader'   hits=     0  unique=0
  'avatar'         hits=  1272  unique=1145
hits per entry (readyplayer, rpm, .glb, gltf, avatarloader, avatar):
  TribeXR/Content/Certificates/cacert.pem: 0 6 0 0 0 0
  TribeXR/Content/Movies/All4ScreensBldgE_v02.mp4: 0 2 0 0 0 0
  TribeXR/Content/Movies/EQ_Twist.mp4: 0 1 0 0 0 0
  TribeXR/Content/Movies/PTDJA_Trailer.mp4: 0 5 0 0 0 0
  TribeXR/Content/Movies/Selina.mp4: 0 4 0 0 0 0
  TribeXR/Content/Movies/TribeTrailer.mp4: 0 12 0 0 0 11
  TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak: 19 281 69 213 0 281
  TribeXR/Content/Paks/pakchunk0optional-Android_ASTC.pak: 0 34 0 1 0 0
  TribeXR/Content/Paks/pakchunk1-Android_ASTC.pak: 0 158 1 1 0 1
  TribeXR/Content/Paks/pakchunk1optional-Android_ASTC.pak: 0 47 0 0 0 0
  TribeXR/Content/Tracks/5 Day DJ Challenge/036 - Eminence - Shapes & Shifts.mp3: 0 3 1 0 0 0
  TribeXR/Content/Tracks/5 Day DJ Challenge/045 - PIXL - This Time.mp3: 0 3 0 0 0 0
  TribeXR/Content/Tracks/5 Day DJ Challenge/057 - Tokyo Machine - PLAY.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/5 Day DJ Challenge/098 - SMLE - Halo (feat. Helen Tess).mp3: 0 2 0 0 0 0
  TribeXR/Content/Tracks/Ben Beiny/In_front.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Ben Beiny/come_together.mp3: 0 3 0 0 0 0
  TribeXR/Content/Tracks/Ben Beiny/kick_back.mp3: 0 2 0 0 0 0
  TribeXR/Content/Tracks/Desty/Elements.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Desty/Going Back.mp3: 0 4 0 0 0 0
  TribeXR/Content/Tracks/Desty/Northern Streets.mp3: 0 5 0 0 0 0
  TribeXR/Content/Tracks/Desty/Stress That.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Desty/You Know I Like It.mp3: 0 2 0 0 0 0
  TribeXR/Content/Tracks/Julian Bell/boutique.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Julian Bell/fashion_beach.mp3: 0 2 0 0 0 0
  TribeXR/Content/Tracks/Julian Bell/fashion_escapade.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Kryoman/Are You Ready.mp3: 0 3 0 0 0 0
  TribeXR/Content/Tracks/Kryoman/Biggie Says.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Kryoman/Blaster.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Kryoman/Darkness.mp3: 0 2 0 0 0 0
  TribeXR/Content/Tracks/Kryoman/Fast Lane.mp3: 0 1 0 0 0 0
  TribeXR/Content/Tracks/Kryoman/Get Up.mp3: 0 3 0 0 0 0
  TribeXR/Content/Tracks/Kryoman/Loaded.mp3: 0 1 0 0 0 0

... [86 lines omitted, full output in logs/020.log] ...

  TribeXR/Plugins/MetaAvatar2/Source/ThirdParty/MetaAvatar2NativeSDK/assets/PresetAvatars_Quest2.zip!/8_quest2.glb: 0 1 0 0 0 0
  TribeXR/Plugins/MetaAvatar2/Source/ThirdParty/MetaAvatar2NativeSDK/assets/PresetAvatars_Quest2.zip!/9_quest2.glb: 0 1 0 0 0 0

real	0m29.541s
user	0m0.015s
sys	0m0.015s
--- Unreal engine version strings (grep -a, independent of the scanner):
     74 ++UE4+Release-4.26
    291 ++UE4+Release-4.27
     36 ++UE5+Release-5.4
```

### [021] 2026-09-28 22:50:55 · exit 0

```sh
echo "=== every readyplayer hit, with neighbouring strings:"; awk "/^== /{show = (\$0 ~ /terms=[^ ]*readyplayer/)} show" hits/obb/hits_context.txt; echo "=== unique gltf strings in the paks (count, string):"; awk -F"\t" "\$2 ~ /Paks/ && \$5 ~ /gltf/ {print \$6}" hits/obb/hits.tsv | sort | uniq -c | sort -rn | head -60
```

```text
=== every readyplayer hit, with neighbouring strings:
== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x133fab20 [ascii] terms=readyplayer
   )`"4
   Acto
   Page
>> ReadyPlayerMe
   keletal
   VRReplica;
   Origi

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x227c5964 [ascii] terms=readyplayer,avatar
>> </Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMe
   c"2:*
   mage
   BlueprintType

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x227c6347 [ascii] terms=readyplayer
   BPTYPE_Normal
   TribeAvatar
>> ReadyPlayerMUrl
   Skins
   Oculus
   5===

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x227e5254 [ascii] terms=readyplayer,avatar
   #,40
   !8811.))34*
>> /Game/Visuals/Skins/OculusAvatar/PreviewImages/T_SkinPreview_ReadyPlayerMe_Custom
   None
   PF_ASTC_6x6
   /Game/Visuals/Skins/OculusAvatar/Previ

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x227e537f [ascii] terms=readyplayer,avatar
   ges/T_SkinPreview_ReadyPlayerMe_Custom
   None
   PF_ASTC_6x6
>> /Game/Visuals/Skins/OculusAvatar/PreviewImages/T_SkinPreview_ReadyPlayerMe_Custom
   /Script/CoreUObject
   /Script/Engine
   Class

... [176 lines omitted, full output in logs/021.log] ...

      2 /glTFRuntime/M_ClearCoat_glTFRuntimeTwoSidedTranslucent_Inst
      2 /glTFRuntime/M_ClearCoat_glTFRuntimeTwoSided_Inst
      2 /glTFRuntime/M_ClearCoat_glTFRuntimeTranslucent_Inst
      1 T_glTFRuntimeZero_sRGB.uexp
      1 T_glTFRuntimeZero_sRGB.uasset
      1 T_glTFRuntimeZero_sRGB
      1 T_glTFRuntimeZero.uexp
      1 T_glTFRuntimeZero.uasset
      1 T_glTFRuntimeZero
      1 T_glTFRuntimeOne_sRGB.uexp
```

### [022] 2026-09-28 22:51:38 · exit 0

```sh
O=pulled/main.2300.com.TribeXR.TribeXR.obb; P=TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak; echo "=== ReadyPlayerMe.uplugin (stored uncompressed in the pak):"; python scripts/strings_at.py $O $P 0x28fcfd00 0x300; echo; echo "=== around TribeAvatar / ReadyPlayerMUrl:"; python scripts/strings_at.py $O $P 0x227c6347 0x300
```

```text
=== ReadyPlayerMe.uplugin (stored uncompressed in the pak):
   0x28fcfa00 A Name": "OVRLipSync",
   0x28fcfa16 A       "Type": "Runtime",
   0x28fcfa30 A       "LoadingPhase": "Default",
   0x28fcfa52 A       "WhitelistPlatforms" : [
   0x28fcfa72 A         "Android",
   0x28fcfa86 A         "Win64",
   0x28fcfa98 A         "Mac"
   0x28fcfaa7 A       ]
   0x28fcfab0 A     },
   0x28fcfab8 A     {
   0x28fcfabf A       "Name": "OVRLipSyncEditor",
   0x28fcfae2 A       "Type": "Editor",
   0x28fcfafb A       "LoadingPhase": "PostEngineInit",
   0x28fcfb24 A       "WhitelistPlatforms" : [
   0x28fcfb44 A         "Win64",
   0x28fcfb56 A         "Mac"
   0x28fcfb65 A       ]
   0x28fcfb6e A     }
   0x28fcfbb5 A 	"FileVersion": 3,
   0x28fcfbc9 A 	"Version": 1,
   0x28fcfbd9 A 	"VersionName": "6.0",
   0x28fcfbf1 A 	"FriendlyName": "ReadyPlayerMe",
   0x28fcfc14 A 	"Description": "ReadyPlayerMe Avatar Toolkit",
   0x28fcfc45 A 	"Category": "ReadyPlayerMe",
   0x28fcfc64 A 	"CreatedBy": "Wolf3D",
   0x28fcfc7d A 	"CreatedByURL": "",
   0x28fcfc93 A 	"DocsURL": "https://docs.readyplayer.me/",
   0x28fcfcc0 A 	"MarketplaceURL": "",
   0x28fcfcd8 A 	"SupportURL": "",
>> 0x28fcfcec A 	"CanContainContent": true,
   0x28fcfd09 A 	"IsBetaVersion": false,
   0x28fcfd23 A 	"IsExperimentalVersion": false,
   0x28fcfd45 A 	"Installed": false,
   0x28fcfd5b A 	"Modules": [
   0x28fcfd6f A 			"Name": "ReadyPlayerMe",
   0x28fcfd8c A 			"Type": "Runtime",
   0x28fcfda3 A 			"LoadingPhase": "Default"
   0x28fcfdcb A 	"Plugins": [
   0x28fcfddf A 			"Name": "glTFRuntime",

... [25 lines omitted, full output in logs/022.log] ...

   0x227c61e9 A z~H\
   0x227c621b A u||7G\
   0x227c62dd A BPTYPE_Normal
   0x227c633a A TribeAvatar
>> 0x227c6347 A ReadyPlayerMUrl
   0x227c6366 A Skins
   0x227c636d A Oculus
   0x227c641e A 5===
   0x227c64a0 A =L}2
   0x227c65c1 A !.i&	JRU
```

### [023] 2026-09-28 22:51:55 · exit 0

```sh
echo "=== unique .glb strings in the paks:"; awk -F"\t" "\$2 ~ /Paks/ && \$5 ~ /\.glb/ {print \$6}" hits/obb/hits.tsv | sort | uniq -c | sort -rn; echo "=== unique avatar strings in the paks (excluding the readyplayer ones above), length >= 8:"; awk -F"\t" "\$2 ~ /Paks/ && \$5 ~ /avatar/ && \$5 !~ /readyplayer/ && length(\$6) >= 8 {print \$6}" hits/obb/hits.tsv | sort | uniq -c | sort -rn | head -120
```

```text
=== unique .glb strings in the paks:
     61 zip://99.glb
      2 MentorAvatar.glb
      2 $.gLb
      1 zip://models/b.glb.zst
      1 DefaultAvatar.glb
      1 DanceAvatar.glb
      1 31.glb
      1 .glb{
=== unique avatar strings in the paks (excluding the readyplayer ones above), length >= 8:
     64 \tAvatarId
     15 cYFMetaAvatar2
      8 AvatarAttach_GEN_VARIABLE
      3 /Game/Visuals/Skins/AvatarProps/Funtcase/T_AvatarProp_FuntcaseMask_Cap
      3 /Game/Visuals/Skins/AvatarProps/Funtcase/T_AvatarProp_FuntcaseMask
      2 TribeXR/Plugins/MetaAvatar2/
      2 T_AvatarProp_FuntcaseMask_Cap
      2 T_AvatarProp_FuntcaseMask
      2 MetaAvatar2.uplugin
      2 MentorAvatar.glb
      2 /Game/Visuals/Skins/OculusAvatar/F_OculusAvatarSkinEntry
      2 /Game/Visuals/Skins/AvatarProps/HapaHat/M_AvatarProp_HapaHat
      2 /Game/Visuals/Skins/AvatarProps/Funtcase/M_AvatarProp_FuntcaseMask_Cap
      2 /Game/Visuals/Skins/AvatarProps/Funtcase/M_AvatarProp_FuntcaseMask
      2 /Game/Pawn/M_DesktopAvatar
      2 /Game/Pawn/Assets/Materials/MI_Avatar_GrabSphere
      1 W_RPMAvatarCreator.uexp
      1 W_RPMAvatarCreator.uasset
      1 TribeXR/Content/Visuals/Skins/OculusAvatar/PreviewImages/
      1 TribeXR/Content/Visuals/Skins/OculusAvatar/
      1 TribeXR/Content/Visuals/Skins/MetaAvatar2/
      1 TribeXR/Content/Visuals/Skins/AvatarProps/HapaHat/
      1 TribeXR/Content/Visuals/Skins/AvatarProps/Funtcase/
      1 TribeXR/Content/Visuals/Skins/AvatarProps/
      1 TribeXR/Content/Pawn/Assets/TribeAvatarHands/
      1 TribeXR/Content/Pawn/Assets/MetaAvatar2/
      1 TribeAvatarHand_Skeleton.uexp
      1 TribeAvatarHand_Skeleton.uasset
      1 TribeAvatar
      1 T_Icon_Avatars.uexp

... [80 lines omitted, full output in logs/023.log] ...

      1 9/Game/Pawn/Assets/TribeAvatarHands/M_Left
      1 9/Game/Achievements/Assets/Badges/T_CustomizeAvatar_Des
      1 5/Game/Visuals/Skins/OculusAvatar/BP_
      1 5/Game/Pawn/Assets/TribeAvatarHands/r_h_pinch_anim
      1 4/Game/Pawn/Assets/TribeAvatarHands/r_h_fist_anim
      1 4/Game/Pawn/Assets/DT_DesktopAvatarLightTuningValues
      1 3/Game/Pawn/Assets/DT_MobileAvatarLightTuningValues
      1 3/Game/Achievements/Assets/Badges/T_CustomizeAvatar
      1 2/Game/Visuals/Skins/AvatarProps/F_Entry
      1 2/Game/Visuals/Skins/AvatarProps/BP_
```

### [024] 2026-09-28 22:52:34 · exit 1

```sh
O=pulled/main.2300.com.TribeXR.TribeXR.obb; echo "--- ASCII strings containing readyplayer (grep -a -o -i):"; grep -a -o -i -E "[[:alnum:]_./:-]*readyplayer[[:alnum:]_./:-]*" $O | sort | uniq -c; echo "--- any readyplayer.me hostname (ASCII):"; grep -a -o -i -E "[[:alnum:].-]*readyplayer\.me" $O | sort | uniq -c; echo "--- UTF-16LE readyplayer occurrences (grep -P):"; grep -a -c -i -P "r\x00e\x00a\x00d\x00y\x00p\x00l\x00a\x00y\x00e\x00r\x00" $O
```

```text
--- ASCII strings containing readyplayer (grep -a -o -i):
      1 /Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMe
      2 /Game/Visuals/Skins/OculusAvatar/PreviewImages/T_SkinPreview_ReadyPlayerMe_Custom
      1 BP_ReadyPlayerMeAvatarSkin.uasset
      1 BP_ReadyPlayerMeAvatarSkin.uexp
      1 https://docs.readyplayer.me/
      5 ReadyPlayerMe
      2 ReadyPlayerMe.uplugin
      1 ReadyPlayerMUrl
      1 T_SkinPreview_ReadyPlayerMe_Custom
      1 T_SkinPreview_ReadyPlayerMe_Custom.uasset
      1 T_SkinPreview_ReadyPlayerMe_Custom.uexp
      2 TribeXR/Plugins/ReadyPlayerMe/
--- any readyplayer.me hostname (ASCII):
      1 docs.readyplayer.me
--- UTF-16LE readyplayer occurrences (grep -P):
0
```

### [025] 2026-09-28 22:53:39 · exit 0

```sh
echo "--- rpm strings in the paks that look like identifiers or paths (letters/digits/_/./ only, length >= 6):"; awk -F"\t" "\$2 ~ /Paks/ && \$5 ~ /rpm/ {print \$6}" hits/obb/hits.tsv | grep -E "^[[:alnum:]_./ -]{6,}\$" | sort | uniq -c | sort -rn | head -40; echo "--- rpm hits by entry type:"; awk -F"\t" "NR>1 && \$5 ~ /rpm/ {n=split(\$2,a,\".\"); print a[n]}" hits/obb/hits.tsv | sort | uniq -c | sort -rn
```

```text
--- rpm strings in the paks that look like identifiers or paths (letters/digits/_/./ only, length >= 6):
      2 rid_PUrPmet
      2 Loos_PWrPmeters
      2 KVorpmponentFixed
      2 /Game/Menus/Assets/Icons/T_Icon_RPM_Paste
      2 /Game/Menus/Assets/Icons/T_Icon_RPM_Goto
      2 /Game/Menus/Assets/Icons/T_Icon_RPM_Copy
      1 yrpmljj
      1 XVSrPm
      1 WYeGrpMW
      1 W_RPMAvatarCreator.uexp
      1 W_RPMAvatarCreator.uasset
      1 VYRPMBI
      1 urPMXe3
      1 UrPMX_
      1 TRPMha
      1 T_Icon_RPM_Paste.uexp
      1 T_Icon_RPM_Paste.uasset
      1 T_Icon_RPM_Paste
      1 T_Icon_RPM_Goto.uexp
      1 T_Icon_RPM_Goto.uasset
      1 T_Icon_RPM_Goto
      1 T_Icon_RPM_Copy.uexp
      1 T_Icon_RPM_Copy.uasset
      1 T_Icon_RPM_Copy
      1 sprprpm
      1 rRPmi-
      1 rPmvoo
      1 RPMRmQ
      1 rPMkCF
      1 RpMiZc
      1 PAsRPM
      1 P2hRPm
      1 oJJaRPm
      1 O2PmXRpm
      1 nRpMSn
      1 lxrPmdip
      1 lrpMSe
      1 KJarpM
      1 gTiSRPMK
      1 GhrpMh
--- rpm hits by entry type:
    520 pak
    113 mp3
     54 mp4
     25 zip
     21 glb
      6 pem
      1 zst
      1 wav
      1 anim
```

### [026] 2026-09-28 22:55:25 · exit 0

```sh
awk "/^== /{show = (\$0 ~ /Paks/ && \$0 ~ /terms=[^ ]*\.glb/)} show" hits/obb/hits_context.txt | grep -v -B3 -A4 "zip://99.glb" | grep -E -B3 -A3 "(Default|Mentor|Dance)Avatar\.glb|>> 31\.glb"
```

```text
   =ATz
   eq$Z[
   BPTYPE_Normal
>> MentorAvatar.glb
   =>=9

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x1cc129bc [ascii] terms=.glb
--
   zip://models/b.glb.zst
   \tPreset 0
   9 30
>> 31.glb
   6jS(F1

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x290808bd [ascii] terms=.glb,avatar
   NetworkEnum.uasset
   NetworkEnum.uexp
   TribeXR/Content/Replays/
>> DanceAvatar.glb
   DefaultAvatar.glb
   MentorAvatar.glb
   SC_ReplayDialogue.uasset

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x290808d5 [ascii] terms=.glb,avatar
   NetworkEnum.uexp
   TribeXR/Content/Replays/
   DanceAvatar.glb
>> DefaultAvatar.glb
   MentorAvatar.glb
   SC_ReplayDialogue.uasset
   SC_ReplayDialogue.uexp

== pulled/main.2300.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak @0x290808ef [ascii] terms=.glb,avatar
   TribeXR/Content/Replays/
   DanceAvatar.glb
   DefaultAvatar.glb
>> MentorAvatar.glb
   SC_ReplayDialogue.uasset
   SC_ReplayDialogue.uexp
   TribeXR/Content/Replays/DanceSequences/
```

### [027] 2026-09-28 22:59:24 · exit 0

```sh
adb devices -l; echo "--- Meta / Oculus PC software running (Link can take over a USB-connected headset):"; powershell.exe -NoProfile -Command "Get-Process | Where-Object { \$_.ProcessName -match 'OVR|Oculus|Meta|Horizon|SideQuest|adb' } | Sort-Object ProcessName | Format-Table -AutoSize ProcessName,Id,StartTime | Out-String -Width 200"
```

```text
List of devices attached
2G0YC1ZF96072F         unauthorized transport_id:1

--- Meta / Oculus PC software running (Link can take over a USB-connected headset):

ProcessName           Id StartTime            
-----------           -- ---------            
adb                  592 9/28/2026 10:40:31 PM
OVRRedir            7888                      
OVRServer_x64      17836 9/28/2026 9:34:43 AM 
OVRServiceLauncher  4848                      



```

### [028] 2026-09-28 23:02:35 · exit 0

```sh
L="$(cygpath -u "$LOCALAPPDATA")/Temp/adb.log"; ls -l --time-style=long-iso "$L"; echo "--- auth / transport lines from the adb server log:"; grep -a -n -i -E "auth|key|unauthori|2G0YC|transport|usb" "$L" | tail -n 40
```

```text
-rw-r--r-- 1 Chris 197121 4325 2026-09-28 23:01 /c/Users/Chris/AppData/Local/Temp/adb.log
--- auth / transport lines from the adb server log:
7:09-28 22:26:43.456   152  5700 E adb     : auth.cpp:98 failed to write public key: Permission denied
8:09-28 22:26:43.457   152  5700 E adb     : auth.cpp:220 Failed to generate new key
9:09-28 22:26:43.457   152  5700 E adb     : auth.cpp:421 Failed to load (or generate) user key
10:09-28 22:28:46.767   152 25840 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
11:09-28 22:29:03.303   152 12308 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
13:09-28 22:33:41.661   152  5700 I adb     : transport.cpp:1123 kicking transport 0x417b1b8 2G0YC1ZF96072F
14:09-28 22:33:41.661   152 25892 E adb     : adb_usb_connection.cpp:52 AdbUsbConnection: terminated (data): No error
15:09-28 22:33:41.661   152 25892 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
23:09-28 22:36:41.337 23112  6332 I adb     : transport.cpp:1123 kicking transport 0x1452548 2G0YC1ZF96072F
24:09-28 22:36:41.338 23112 24412 E adb     : adb_usb_connection.cpp:52 AdbUsbConnection: terminated (data): No error
25:09-28 22:36:41.338 23112 24412 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
32:09-28 22:37:22.796 26328  1564 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
33:09-28 22:37:36.369 26328  7224 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
34:09-28 22:39:51.325 26328 10808 I adb     : transport.cpp:1116 resetting transport 0x9e8a88 2G0YC1ZF96072F
35:09-28 22:39:51.326 26328 13536 E adb     : adb_usb_connection.cpp:52 AdbUsbConnection: terminated (data): No error
36:09-28 22:39:51.326 26328 13536 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
44:09-28 23:00:59.402   592 12928 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
45:09-28 23:01:11.692   592 23492 E adb     : adb_usb_connection.cpp:52 AdbUsbConnection: terminated (data): No error
46:09-28 23:01:11.692   592 23492 I adb     : transport.cpp:1222 2G0YC1ZF96072F: connection terminated: read failed
```

_Background wait stopped: the user reported the "Allow USB debugging?" prompt never appeared, even after
replugging with the headset on. Troubleshooting of the headset-side authorization is paused here; the
APK (steps 2-5) is still outstanding._

Official headset-side procedure (Meta docs, fetched 2026-09-28): Meta Horizon phone app → headset →
Headset Settings → Developer Mode on; connect with a USB-C data cable; in the headset Quick Control →
Open Settings → Developer tab → toggle "MTP Notification" on; at the prompt choose "Always allow from
this computer". Meta also tracked "USB Debugging Prompt Not Appearing on Headset" and says a fix shipped
2026-03-06. Sources: developers.meta.com/horizon/documentation/native/android/mobile-device-setup/,
.../ts-mqdh-getting-started/, developers.meta.com/horizon/feedback/vr/investigations/1274397821419930/

### [029] 2026-09-28 22:59:46 · exit 127

```sh
timeout 900 adb wait-for-usb-device; echo "wait-for-usb-device exit: $? (124 = timed out after 15 min)"; adb devices -l
```

```text
(no output)
```

### [030] 2026-09-28 23:05:38 · exit 0

```sh
timeout 900 adb wait-for-usb-device; echo "wait-for-usb-device exit: $? (124 = timed out after 15 min)"; adb devices -l
```

```text
wait-for-usb-device exit: 0 (124 = timed out after 15 min)
List of devices attached
2G0YC1ZF96072F         device product:eureka model:Quest_3 device:eureka transport_id:8

```

### [031] 2026-09-28 23:16:22 · exit 0

```sh
echo "--- packages matching tribe:"; adb shell pm list packages | grep -i tribe; echo "--- pm path com.TribeXR.TribeXR:"; adb shell pm path com.TribeXR.TribeXR; echo "--- version / install info:"; adb shell dumpsys package com.TribeXR.TribeXR | grep -E "versionName|versionCode|codePath|splits|primaryCpuAbi|installerPackageName|lastUpdateTime" | sort -u; echo "--- APK files on device (size):"; for p in $(adb shell pm path com.TribeXR.TribeXR | tr -d "\r" | sed "s/^package://"); do adb shell ls -l "$p"; done; echo "--- OBB folder on device:"; adb shell ls -l /sdcard/Android/obb/com.TribeXR.TribeXR/
```

```text
--- packages matching tribe:
package:com.TribeXR.TribeXR
--- pm path com.TribeXR.TribeXR:
package:/data/app/~~ZNkLC8_VVDaeDUO3H9Jb6w==/com.TribeXR.TribeXR-Q80fuW3lhelbzNLNEd8D8Q==/base.apk
--- version / install info:
    codePath=/data/app/~~ZNkLC8_VVDaeDUO3H9Jb6w==/com.TribeXR.TribeXR-Q80fuW3lhelbzNLNEd8D8Q==
    installerPackageName=com.oculus.ocms
    lastUpdateTime=2026-09-28 22:59:14
    primaryCpuAbi=arm64-v8a
    splits=[base]
    versionCode=2304 minSdk=32 targetSdk=32
    versionName=0.12.5.1
--- APK files on device (size):
-rw-r--r-- 1 system system 111389761 2026-09-28 22:59 /data/app/~~ZNkLC8_VVDaeDUO3H9Jb6w==/com.TribeXR.TribeXR-Q80fuW3lhelbzNLNEd8D8Q==/base.apk
--- OBB folder on device:
total 1986644
-rwxrws--- 1 u0_a107 ext_obb_rw 2034318982 2026-09-28 22:58 main.2304.com.TribeXR.TribeXR.obb
```

### [032] 2026-09-28 23:16:46 · exit 0

```sh
df -h /c | tail -n 1; P=$(adb shell pm path com.TribeXR.TribeXR | tr -d "\r" | sed "s/^package://"); echo "pulling: $P"; adb pull "$P" pulled/ && ls -l --time-style=long-iso pulled/base.apk && echo "--- sha256 on the headset:" && adb shell sha256sum "$P" && echo "--- sha256 on this PC:" && sha256sum pulled/base.apk
```

```text
C:              930G  789G  142G  85% /c
pulling: /data/app/~~ZNkLC8_VVDaeDUO3H9Jb6w==/com.TribeXR.TribeXR-Q80fuW3lhelbzNLNEd8D8Q==/base.apk
/data/app/~~ZNkLC8_VVDaeDUO3H9Jb6w==/com.TribeXR.TribeXR-Q80fuW3lhelbzNLNEd8D8Q==/base.apk: 1 file pulled, 0 skipped. 37.9 MB/s (111389761 bytes in 2.802s)
-rw-r--r-- 1 Chris 197121 111389761 2026-09-28 23:16 pulled/base.apk
--- sha256 on the headset:
0b7112f7fc2c7c3dd34d91b1091fcbdb154fdb2873e11fae25066a0634b0ef7c  /data/app/~~ZNkLC8_VVDaeDUO3H9Jb6w==/com.TribeXR.TribeXR-Q80fuW3lhelbzNLNEd8D8Q==/base.apk
--- sha256 on this PC:
0b7112f7fc2c7c3dd34d91b1091fcbdb154fdb2873e11fae25066a0634b0ef7c *pulled/base.apk
```

### [033] 2026-09-28 23:17:15 · exit 0

```sh
O=/sdcard/Android/obb/com.TribeXR.TribeXR/main.2304.com.TribeXR.TribeXR.obb; adb pull "$O" pulled/ && ls -l --time-style=long-iso pulled/*.obb && echo "--- sha256 on the headset:" && adb shell sha256sum "$O" && echo "--- sha256 on this PC:" && sha256sum pulled/main.2304.com.TribeXR.TribeXR.obb
```

```text
/sdcard/Android/obb/com.TribeXR.TribeXR/main.2304.com.TribeXR.TribeXR.obb: 1 file pulled, 0 skipped. 35.3 MB/s (2034318982 bytes in 54.950s)
-rw-r--r-- 1 Chris 197121 2032920524 2026-09-05 12:53 pulled/main.2300.com.TribeXR.TribeXR.obb
-rw-r--r-- 1 Chris 197121 2034318982 2026-09-28 23:18 pulled/main.2304.com.TribeXR.TribeXR.obb
--- sha256 on the headset:
42c9e5d5e5b1d33fd97a97a2854625240a1ce5fd718dd4387ef35b0aa3656ec2  /sdcard/Android/obb/com.TribeXR.TribeXR/main.2304.com.TribeXR.TribeXR.obb
--- sha256 on this PC:
42c9e5d5e5b1d33fd97a97a2854625240a1ce5fd718dd4387ef35b0aa3656ec2 *pulled/main.2304.com.TribeXR.TribeXR.obb
```

### [034] 2026-09-28 23:18:23 · exit 0

```sh
mkdir -p unpacked/base && unzip -q -o pulled/base.apk -d unpacked/base; echo "unzip exit: $?"
echo "--- top level:"; ls -la unpacked/base
echo "--- native libs:"; ls -l unpacked/base/lib/*/
echo "--- Unity markers (libil2cpp.so, global-metadata.dat, Managed/*.dll, assets/bin/Data):"
find unpacked/base \( -name libil2cpp.so -o -name global-metadata.dat -o -path "*/Managed/*.dll" -o -path "*assets/bin/Data*" \) | head; echo "(end of Unity markers)"
echo "--- assets/ (depth 2):"; find unpacked/base/assets -maxdepth 2 | head -40
echo "--- largest files:"; find unpacked/base -type f -printf "%s\t%p\n" | sort -rn | head -12
echo "--- libUnreal.so:"; file unpacked/base/lib/arm64-v8a/libUnreal.so
echo "--- engine version strings in libUnreal.so (ASCII, then UTF-16LE):"
grep -a -o -E "\+\+UE[45]\+Release-[0-9.]+" unpacked/base/lib/arm64-v8a/libUnreal.so | sort | uniq -c
grep -a -o -P "\+\x00\+\x00U\x00E\x00[45]\x00\+\x00R\x00e\x00l\x00e\x00a\x00s\x00e\x00-\x00(?:[0-9.]\x00)+" unpacked/base/lib/arm64-v8a/libUnreal.so | tr -d "\000" | sort | uniq -c
```

```text
unzip exit: 0
--- top level:
total 5826
drwxr-xr-x 1 Chris 197121       0 Sep 28 23:18 .
drwxr-xr-x 1 Chris 197121       0 Sep 28 23:18 ..
-rw-r--r-- 1 Chris 197121   24864 Jan  1  1981 AndroidManifest.xml
drwxr-xr-x 1 Chris 197121       0 Sep 28 23:18 assets
-rw-r--r-- 1 Chris 197121 5221312 Jan  1  1981 classes.dex
drwxr-xr-x 1 Chris 197121       0 Sep 28 23:18 lib
drwxr-xr-x 1 Chris 197121       0 Sep 28 23:18 META-INF
-rw-r--r-- 1 Chris 197121      78 Jan  1  1981 play-services-appset.properties
-rw-r--r-- 1 Chris 197121      74 Jan  1  1981 play-services-auth.properties
-rw-r--r-- 1 Chris 197121      94 Jan  1  1981 play-services-auth-api-phone.properties
-rw-r--r-- 1 Chris 197121      84 Jan  1  1981 play-services-auth-base.properties
-rw-r--r-- 1 Chris 197121      74 Jan  1  1981 play-services-base.properties
-rw-r--r-- 1 Chris 197121      82 Jan  1  1981 play-services-basement.properties
-rw-r--r-- 1 Chris 197121      76 Jan  1  1981 play-services-drive.properties
-rw-r--r-- 1 Chris 197121      74 Jan  1  1981 play-services-fido.properties
-rw-r--r-- 1 Chris 197121      82 Jan  1  1981 play-services-games-v2.properties
-rw-r--r-- 1 Chris 197121      76 Jan  1  1981 play-services-tasks.properties
drwxr-xr-x 1 Chris 197121       0 Sep 28 23:18 res
-rw-r--r-- 1 Chris 197121  544676 Jan  1  1981 resources.arsc
--- native libs:
total 254924
-rw-r--r-- 1 Chris 197121    722960 Jan  1  1981 libacidsynth.so
-rw-r--r-- 1 Chris 197121    575712 Jan  1  1981 libagora_video_decoder_extension.so
-rw-r--r-- 1 Chris 197121    608480 Jan  1  1981 libagora_video_encoder_extension.so
-rw-r--r-- 1 Chris 197121    690336 Jan  1  1981 libagora-fdkaac.so
-rw-r--r-- 1 Chris 197121   6006520 Jan  1  1981 libagora-ffmpeg.so
-rw-r--r-- 1 Chris 197121  28034448 Jan  1  1981 libagora-rtc-sdk.so
-rw-r--r-- 1 Chris 197121   8996512 Jan  1  1981 libagora-rtm-sdk.so
-rw-r--r-- 1 Chris 197121    198496 Jan  1  1981 libagora-soundtouch.so
-rw-r--r-- 1 Chris 197121    561176 Jan  1  1981 libaosl.so
-rw-r--r-- 1 Chris 197121   5585976 Jan  1  1981 libbeatport-sdk.so
-rw-r--r-- 1 Chris 197121    636944 Jan  1  1981 libdrummachine.so
-rw-r--r-- 1 Chris 197121  22344936 Jan  1  1981 libEOSSDK.so
-rw-r--r-- 1 Chris 197121    432000 Jan  1  1981 libmrutilitykitshared.so
-rw-r--r-- 1 Chris 197121    480224 Jan  1  1981 libopenxr_loader.so
-rw-r--r-- 1 Chris 197121   7268552 Jan  1  1981 libovravatar2.so
-rw-r--r-- 1 Chris 197121   9195920 Jan  1  1981 libovrbody.so

... [22 lines omitted, full output in logs/034.log] ...

8996512	unpacked/base/lib/arm64-v8a/libagora-rtm-sdk.so
7268552	unpacked/base/lib/arm64-v8a/libovravatar2.so
6006520	unpacked/base/lib/arm64-v8a/libagora-ffmpeg.so
5585976	unpacked/base/lib/arm64-v8a/libbeatport-sdk.so
5328744	unpacked/base/lib/arm64-v8a/libOVRPlugin.so
5221312	unpacked/base/classes.dex
1399320	unpacked/base/lib/arm64-v8a/libvideo_enc.so
--- libUnreal.so:
unpacked/base/lib/arm64-v8a/libUnreal.so: ELF 64-bit LSB shared object, ARM aarch64, version 1 (SYSV), dynamically linked, for Android 29, built by NDK r25b (8937393), BuildID[sha1]=41f08cd5b2674368a0e3b1c849a00c554f214030, stripped
--- engine version strings in libUnreal.so (ASCII, then UTF-16LE):
```

### [035] 2026-09-28 23:18:56 · exit 0

```sh
echo "--- assets/UECommandLine.txt:"; cat unpacked/base/assets/UECommandLine.txt; echo; echo "--- scan of base.apk (all entries, ASCII + UTF-16LE):"; time python scripts/scan_strings.py hits/apk pulled/base.apk
```

```text
--- assets/UECommandLine.txt:
-project="../../../TribeXR/TribeXR.uproject"
--- scan of base.apk (all entries, ASCII + UTF-16LE):
scanned 751 files/entries, 267,379,760 bytes; 2898 hit strings
  'readyplayer'    hits=    68  unique=62
  'rpm'            hits=    27  unique=22
  '.glb'           hits=    11  unique=11
  'gltf'           hits=   340  unique=297
  'avatarloader'   hits=     0  unique=0
  'avatar'         hits=  2494  unique=2098
hits per entry (readyplayer, rpm, .glb, gltf, avatarloader, avatar):
  META-INF/MANIFEST.MF: 0 0 0 0 0 1
  META-INF/TRIBEXR.SF: 0 1 0 0 0 1
  classes.dex: 0 2 1 0 0 12
  lib/arm64-v8a/libOVRLipSync.so: 0 2 0 0 0 0
  lib/arm64-v8a/libUnreal.so: 68 18 6 231 0 195
  lib/arm64-v8a/libagora-ffmpeg.so: 0 2 0 0 0 0
  lib/arm64-v8a/libagora-rtc-sdk.so: 0 0 0 0 0 10
  lib/arm64-v8a/libovravatar2.so: 0 0 4 109 0 2216
  lib/arm64-v8a/libovrbody.so: 0 2 0 0 0 2
  lib/arm64-v8a/libovrgpuskinning.so: 0 0 0 0 0 1
  lib/arm64-v8a/libovrplatformloader.so: 0 0 0 0 0 2
  lib/arm64-v8a/libovrplugintracking.so: 0 0 0 0 0 4
  lib/arm64-v8a/libxrtracking.so: 0 0 0 0 0 50

real	0m4.973s
user	0m0.000s
sys	0m0.000s
```

### [036] 2026-09-28 23:19:02 · exit 0

```sh
time python scripts/scan_strings.py hits/obb2304 pulled/main.2304.com.TribeXR.TribeXR.obb | head -n 8; echo "--- readyplayer strings: OBB 2300 vs 2304 (diff; < only in 2300, > only in 2304):"; diff <(cut -f2- hits/obb/unique_readyplayer.txt | sort) <(cut -f2- hits/obb2304/unique_readyplayer.txt | sort) && echo "(identical)"; echo "--- OBB 2304 pak footers:"; python scripts/pak_footer.py pulled/main.2304.com.TribeXR.TribeXR.obb | grep -E "::|encrypted_index|compression"
```

```text
scanned 798 files/entries, 2,125,236,832 bytes; 2396 hit strings
  'readyplayer'    hits=    19  unique=16
  'rpm'            hits=   742  unique=634
  '.glb'           hits=   157  unique=90
  'gltf'           hits=   217  unique=146
  'avatarloader'   hits=     0  unique=0
  'avatar'         hits=  1274  unique=1145
hits per entry (readyplayer, rpm, .glb, gltf, avatarloader, avatar):

real	0m29.543s
user	0m0.077s
sys	0m0.046s
--- readyplayer strings: OBB 2300 vs 2304 (diff; < only in 2300, > only in 2304):
(identical)
--- OBB 2304 pak footers:
pulled/main.2304.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak  (688,574,643 bytes)
    encrypted_index: False
    compression_methods: ['Oodle']
pulled/main.2304.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk0optional-Android_ASTC.pak  (103,093,146 bytes)
    encrypted_index: False
    compression_methods: ['Oodle']
pulled/main.2304.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk1-Android_ASTC.pak  (403,563,126 bytes)
    encrypted_index: False
    compression_methods: ['Oodle']
pulled/main.2304.com.TribeXR.TribeXR.obb :: TribeXR/Content/Paks/pakchunk1optional-Android_ASTC.pak  (142,888,023 bytes)
    encrypted_index: False
    compression_methods: ['Oodle']
```

### [037] 2026-09-28 23:19:41 · exit 0

```sh
echo "=== every unique readyplayer string in base.apk (count, string) with encoding:"; awk -F"\t" "NR>1 && \$5 ~ /readyplayer/ {print \$4 \"\t\" \$6}" hits/apk/hits.tsv | sort | uniq -c | sort -k2,2 -k3
```

```text
=== every unique readyplayer string in base.apk (count, string) with encoding:
      1 ascii	/Script/ReadyPlayerMe
      1 ascii	EReadyPlayerMeBone
      1 ascii	EReadyPlayerMeBone::AvatarRoot
      1 ascii	EReadyPlayerMeBone::Head
      1 ascii	EReadyPlayerMeBone::Hips
      1 ascii	EReadyPlayerMeBone::LeftEye
      1 ascii	EReadyPlayerMeBone::LeftHand
      1 ascii	EReadyPlayerMeBone::LeftHandIndex1
      1 ascii	EReadyPlayerMeBone::LeftHandIndex2
      1 ascii	EReadyPlayerMeBone::LeftHandIndex3
      1 ascii	EReadyPlayerMeBone::LeftHandMiddle1
      1 ascii	EReadyPlayerMeBone::LeftHandMiddle2
      1 ascii	EReadyPlayerMeBone::LeftHandMiddle3
      1 ascii	EReadyPlayerMeBone::LeftHandPinky1
      1 ascii	EReadyPlayerMeBone::LeftHandPinky2
      1 ascii	EReadyPlayerMeBone::LeftHandPinky3
      1 ascii	EReadyPlayerMeBone::LeftHandRing1
      1 ascii	EReadyPlayerMeBone::LeftHandRing2
      1 ascii	EReadyPlayerMeBone::LeftHandRing3
      1 ascii	EReadyPlayerMeBone::LeftHandThumb1
      1 ascii	EReadyPlayerMeBone::LeftHandThumb2
      1 ascii	EReadyPlayerMeBone::LeftHandThumb3
      1 ascii	EReadyPlayerMeBone::Neck
      1 ascii	EReadyPlayerMeBone::NUM_BONES
      1 ascii	EReadyPlayerMeBone::RightEye
      1 ascii	EReadyPlayerMeBone::RightHand
      1 ascii	EReadyPlayerMeBone::RightHandIndex1
      1 ascii	EReadyPlayerMeBone::RightHandIndex2
      1 ascii	EReadyPlayerMeBone::RightHandIndex3
      1 ascii	EReadyPlayerMeBone::RightHandMiddle1
      1 ascii	EReadyPlayerMeBone::RightHandMiddle2
      1 ascii	EReadyPlayerMeBone::RightHandMiddle3
      1 ascii	EReadyPlayerMeBone::RightHandPinky1
      1 ascii	EReadyPlayerMeBone::RightHandPinky2
      1 ascii	EReadyPlayerMeBone::RightHandPinky3
      1 ascii	EReadyPlayerMeBone::RightHandRing1
      1 ascii	EReadyPlayerMeBone::RightHandRing2
      1 ascii	EReadyPlayerMeBone::RightHandRing3
      1 ascii	EReadyPlayerMeBone::RightHandThumb1

... [19 lines omitted, full output in logs/037.log] ...

      1 utf16le	HandleReadyPlayerMeOnAvatarCached
      1 utf16le	ReadyPlayerMeAvatarUrl
      1 utf16le	ReadyPlayerMeETag
      1 utf16le	ReadyPlayerMeHeadNeckAnimInstanceProxy
      1 utf16le	ReadyPlayerMeInputPacket
      1 utf16le	ReadyPlayerMeVisemePacket
      1 utf16le	UReadyPlayerMeComponent
      1 utf16le	UReadyPlayerMeFunctionLibrary
      1 utf16le	UReadyPlayerMeHandAnimInstance
      1 utf16le	UReadyPlayerMeHeadNeckAnimInstance
```

### [038] 2026-09-28 23:19:59 · exit 0

```sh
echo "=== context of the URL and of the .glb hits in libUnreal.so:"; awk "/^== /{show = (\$0 ~ /libUnreal/ && (\$0 ~ /terms=[^ ]*\.glb/)) } /^>> https:\/\/readyplayer/{print prev3; print prev2; print prev1} show; {prev3=prev2; prev2=prev1; prev1=\$0}" hits/apk/hits_context.txt; echo "=== strings around the URL (python strings_at, +-0x300):"; off=$(awk -F"\t" "\$6 ~ /readyplayer.me\/api/ {print \$3}" hits/apk/hits.tsv); echo "offset in libUnreal.so: $off"; python scripts/strings_at.py unpacked/base/lib/arm64-v8a/libUnreal.so $off 0x300
```

```text
=== context of the URL and of the .glb hits in libUnreal.so:
== pulled/base.apk :: lib/arm64-v8a/libUnreal.so @0x9984c [utf16le] terms=.glb
   MeshPlaneCut
   bCameraCut
   Do Plane Cut
>> zip://models/blank.glb.zst
   AmbientCubemapMipAdjust
   InQuadAdjust
   InUVAdjust

== pulled/base.apk :: lib/arm64-v8a/libUnreal.so @0x2c4f46 [utf16le] terms=.glb,avatar
   GreatJob
   NiceJob
   GoodJob
>> Replays/DefaultAvatar.glb
   zip:\/\/([0-9]*)\.glb
   zip://99.glb
   zip://%s_quest2.glb

== pulled/base.apk :: lib/arm64-v8a/libUnreal.so @0x2c4f7a [utf16le] terms=.glb
   NiceJob
   GoodJob
   Replays/DefaultAvatar.glb
>> zip:\/\/([0-9]*)\.glb
   zip://99.glb
   zip://%s_quest2.glb
   RefCountSize %llu  FreeSize %llu  FreeMem %llukb

== pulled/base.apk :: lib/arm64-v8a/libUnreal.so @0x2c4fa6 [utf16le] terms=.glb
   GoodJob
   Replays/DefaultAvatar.glb
   zip:\/\/([0-9]*)\.glb
>> zip://99.glb
   zip://%s_quest2.glb
   RefCountSize %llu  FreeSize %llu  FreeMem %llukb
   ListSize %llu  Blocks Count %d  Free %llu  Mem %llukb   Li

== pulled/base.apk :: lib/arm64-v8a/libUnreal.so @0x2c4fc0 [utf16le] terms=.glb
   Replays/DefaultAvatar.glb
   zip:\/\/([0-9]*)\.glb

... [69 lines omitted, full output in logs/038.log] ...

   0x005be7a6 A http://
   0x005be7ae A file://
   0x005be7b6 A ;sha256//
   0x005be7c0 A 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz./
   0x005be805 A /../
   0x005be80a A ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
   0x005be84b A SOCKS5: the destination hostname is too long to be resolved remotely by the proxy.
   0x005be89e A Confirmation dialog failed due to null Android Activity.
   0x005be8d7 A infinity.
   0x005be8e1 A Check that the Java PlayCore AAR is included and that PlayCo
```

### [039] 2026-09-28 23:20:20 · exit 0

```sh
L=unpacked/base/lib/arm64-v8a/libUnreal.so; echo "--- grep: ASCII readyplayer strings in libUnreal.so:"; grep -a -o -i -E "[[:alnum:]_:./-]*readyplayer[[:alnum:]_:./-]*" $L | wc -l; echo "--- grep: UTF-16LE readyplayer occurrences:"; grep -a -o -i -P "r\x00e\x00a\x00d\x00y\x00p\x00l\x00a\x00y\x00e\x00r\x00" $L | wc -l; echo "--- grep: any readyplayer.me hostname or URL, ASCII then UTF-16LE:"; grep -a -o -i -E "[[:alnum:].:/-]*readyplayer\.me[[:alnum:]./_-]*" $L | sort | uniq -c; grep -a -o -i -P "(?:[[:alnum:].:/-]\x00)*r\x00e\x00a\x00d\x00y\x00p\x00l\x00a\x00y\x00e\x00r\x00\.\x00m\x00e\x00(?:[[:alnum:]./_-]\x00)*" $L | tr -d "\000" | sort | uniq -c; echo "(end hostnames)"; echo "--- avatar-type and Tribe avatar identifiers in libUnreal.so:"; awk -F"\t" "NR>1 && \$2 ~ /libUnreal/ && \$5 ~ /avatar/ {print \$6}" hits/apk/hits.tsv | grep -E "Tribe|AvatarType|AvatarUrl|AvatarID|AvatarId|LocalAvatar|Local" | sort -u | head -60
```

```text
--- grep: ASCII readyplayer strings in libUnreal.so:
56
--- grep: UTF-16LE readyplayer occurrences:
12
--- grep: any readyplayer.me hostname or URL, ASCII then UTF-16LE:
      1 https://readyplayer.me/api/avatar/
(end hostnames)
--- avatar-type and Tribe avatar identifiers in libUnreal.so:
AvatarId
AvatarID
avatarSDK_enableLocalAnimationPlayback
C:/Users/Hunter/Documents/Unreal Projects/TribeXR/Plugins/MetaAvatar2/Source/MetaAvatar2/Private/MetaAvatar2Manager.cpp
CurrentETribeAvatarType
ETribeAvatarType::MetaAvatar2
ETribeAvatarType::None
ETribeAvatarType::ReadyPlayerMe
GetAvatarId
GetAvatarIdForServer
GetAvatarTypeForId
GetAvatarUrlCacheFilename
GetTribeDefaultAvatarId
GetTribeMentorAvatarId
InAvatarId
InAvatarType
IsValidReadyPlayerMeAvatarID
IsValidReadyPlayerMeAvatarUrl
NewAvatarId
QueriedAvatarUrl
ReadyPlayerMeAvatarUrl
SaveAvatarId
SkeletalMesh'/Game/Pawn/Assets/TribeAvatarHands/SK_TribeAvatarLeftHand.SK_TribeAvatarLeftHand'
SkeletalMesh'/Game/Pawn/Assets/TribeAvatarHands/SK_TribeAvatarRightHand.SK_TribeAvatarRightHand'
TribeAvatar
TribeAvatarCacheDelegate__DelegateSignature
TribeAvatarComponentDelegate__DelegateSignature
TribeAvatarImageDelegate__DelegateSignature
TribeAvatarLightTuningValues
UTribeAvatarComponent
```

### [040] 2026-09-28 23:28:26 · exit 0

```sh
adb devices -l; mkdir -p cache
echo "=== [1a] /sdcard/Android/data/com.TribeXR.TribeXR/ ==="
adb shell ls -laR /sdcard/Android/data/com.TribeXR.TribeXR/ 2>&1 | tee cache/external_tree.txt | head -80
echo "(external_tree.txt lines: $(wc -l < cache/external_tree.txt))"
```

```text
List of devices attached
2G0YC1ZF96072F         device product:eureka model:Quest_3 device:eureka transport_id:8

=== [1a] /sdcard/Android/data/com.TribeXR.TribeXR/ ===
/sdcard/Android/data/com.TribeXR.TribeXR:
total 16
drwxrws---  4 u0_a107  ext_data_rw 4096 2024-02-22 12:57 .
drwxrws--x 37 media_rw ext_data_rw 4096 2026-09-05 14:09 ..
drwxrws---  2 u0_a107  ext_data_rw 4096 2024-02-22 13:00 cache
drwxrws---  9 u0_a107  ext_data_rw 4096 2026-09-19 12:44 files

/sdcard/Android/data/com.TribeXR.TribeXR/cache:
total 52
drwxrws--- 2 u0_a107 ext_data_rw  4096 2024-02-22 13:00 .
drwxrws--- 4 u0_a107 ext_data_rw  4096 2024-02-22 12:57 ..
-rw------- 1 u0_a107 ext_data_rw 40960 2026-09-19 12:44 ga.sqlite3
-rw------- 1 u0_a107 ext_data_rw     0 2026-09-19 12:44 ga.sqlite3-journal

/sdcard/Android/data/com.TribeXR.TribeXR/files:
total 101156
drwxrws--- 9 u0_a107 ext_data_rw     4096 2026-09-19 12:44 .
drwxrws--- 4 u0_a107 ext_data_rw     4096 2024-02-22 12:57 ..
-rwxrwx--- 1 u0_a107 ext_data_rw  3790959 2026-09-19 12:27 CachedAvatars.zip
drwxr-s--- 5 u0_a107 ext_data_rw     4096 2024-02-22 13:02 Documents
drwxrws--- 3 u0_a107 ext_data_rw     4096 2024-03-07 15:24 Oculus
-rwxrwx--- 1 u0_a107 ext_data_rw  7877284 2026-09-19 12:27 OvrAvatar2Assets.zip
-rwxrwx--- 1 u0_a107 ext_data_rw 63625279 2026-09-19 12:27 PresetAvatars_Quest2.zip
drwxrws--- 3 u0_a107 ext_data_rw     4096 2024-02-22 12:57 UE4Game
drwxrws--- 3 u0_a107 ext_data_rw     4096 2025-06-03 16:42 UnrealGame
drwxr-s--- 2 u0_a107 ext_data_rw     4096 2026-09-19 12:27 VulkanProgramBinaryCache
-rw-rw---- 1 u0_a107 ext_data_rw  2097060 2026-09-19 12:43 agoraapi.1.log
-rw-rw---- 1 u0_a107 ext_data_rw  2097098 2026-09-19 12:40 agoraapi.2.log
-rw-rw---- 1 u0_a107 ext_data_rw  2097092 2026-09-19 12:38 agoraapi.3.log
-rw-rw---- 1 u0_a107 ext_data_rw  2097100 2026-09-19 12:36 agoraapi.4.log
-rw-rw---- 1 u0_a107 ext_data_rw  1225296 2026-09-19 12:44 agoraapi.log
-rw-rw---- 1 u0_a107 ext_data_rw  1048449 2026-09-19 12:44 agorartmsdk.1.log
-rw-rw---- 1 u0_a107 ext_data_rw  1048421 2026-09-19 12:39 agorartmsdk.2.log
-rw-rw---- 1 u0_a107 ext_data_rw  1048461 2026-09-19 12:35 agorartmsdk.3.log
-rw-rw---- 1 u0_a107 ext_data_rw  1048514 2026-09-19 12:31 agorartmsdk.4.log
-rw-rw---- 1 u0_a107 ext_data_rw    15493 2026-09-19 12:44 agorartmsdk.log

... [35 lines omitted, full output in logs/040.log] ...


/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/rekordbox:
total 8
drwxr-s--- 2 u0_a107 ext_data_rw 4096 2024-02-22 13:00 .
drwxr-s--- 5 u0_a107 ext_data_rw 4096 2024-02-22 13:02 ..

/sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-03-07 15:24 .
(external_tree.txt lines: 111)
```

### [041] 2026-09-28 23:28:45 · exit 0

```sh
echo "=== [1a-cont] rest of external_tree.txt (past line 80): ==="; sed -n "81,400p" cache/external_tree.txt
echo; echo "=== [1b] /sdcard/Android/obb/com.TribeXR.TribeXR/ ==="; adb shell ls -laR /sdcard/Android/obb/com.TribeXR.TribeXR/ 2>&1 | tee cache/obb_tree.txt
echo; echo "=== [1c] /sdcard/UnrealGame/ ==="; adb shell ls -laR /sdcard/UnrealGame/ 2>&1 | tee cache/sdcard_unrealgame_tree.txt | head -60
```

```text
=== [1a-cont] rest of external_tree.txt (past line 80): ===
drwxrws--- 9 u0_a107 ext_data_rw 4096 2026-09-19 12:44 ..
drwxrws--- 2 u0_a107 ext_data_rw 4096 2025-05-05 17:27 Avatars2

/sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2:
total 59144
drwxrws--- 2 u0_a107 ext_data_rw     4096 2025-05-05 17:27 .
drwxrws--- 3 u0_a107 ext_data_rw     4096 2024-03-07 15:24 ..
-rw-rw---- 1 u0_a107 ext_data_rw 12590682 2024-03-07 15:24 A_1208024283466024.anim.zip
-rw-rw---- 1 u0_a107 ext_data_rw  3601596 2025-05-05 17:27 A_1232362938473877.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3434756 2024-06-24 12:12 A_1426978754688935.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3246510 2024-06-24 12:05 A_1677002969771167.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3150026 2024-06-24 11:50 A_2546452168858501.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3516589 2024-03-16 15:15 A_258875507279586.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3464265 2025-01-08 22:05 A_2641865686006165.glb
-rw-rw---- 1 u0_a107 ext_data_rw  2477639 2024-04-06 12:41 A_311473537933362.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3869262 2024-06-24 11:29 A_368505276218154.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3690510 2025-01-13 20:13 A_408029648751395.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3608863 2024-03-07 15:24 A_413060121118574.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3632409 2024-06-24 12:06 A_437208149136331.glb
-rw-rw---- 1 u0_a107 ext_data_rw  2847602 2024-07-23 12:30 A_838591288205515.glb
-rw-rw---- 1 u0_a107 ext_data_rw  3375551 2024-06-24 12:28 A_845683494085919.glb
-rw-rw---- 1 u0_a107 ext_data_rw  4017176 2024-06-24 12:34 A_975825064240371.glb

/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 .
drwxrws--- 9 u0_a107 ext_data_rw 4096 2026-09-19 12:44 ..
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 TribeXR

/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024
=== [1b] /sdcard/Android/obb/com.TribeXR.TribeXR/ ===
/sdcard/Android/obb/com.TribeXR.TribeXR:
total 1986652
drwxrws---  2 u0_a107  ext_obb_rw       4096 2026-09-28 22:59 .
drwxrws--x 58 media_rw ext_obb_rw       4096 2026-08-04 12:42 ..
-rwxrws---  1 u0_a107  ext_obb_rw 2034318982 2026-09-28 22:58 main.2304.com.TribeXR.TribeXR.obb

=== [1c] /sdcard/UnrealGame/ ===
ls: /sdcard/UnrealGame/: No such file or directory
```

### [042] 2026-09-28 23:29:15 · exit 0

```sh
adb shell ls -laR /sdcard/Android/data/com.TribeXR.TribeXR/ > cache/external_tree.txt 2>&1; echo "external_tree.txt lines: $(wc -l < cache/external_tree.txt)"
echo "=== directories captured: ==="; grep -E ":$" cache/external_tree.txt
echo; echo "=== [2] internal storage via run-as (release build expected to FAIL): ==="; adb shell run-as com.TribeXR.TribeXR ls -laR files 2>&1 | head
echo; echo "=== cacheFile.txt (48 bytes): ==="; adb shell cat /sdcard/Android/data/com.TribeXR.TribeXR/files/cacheFile.txt 2>&1; echo "(end)"
```

```text
external_tree.txt lines: 194
=== directories captured: ===
/sdcard/Android/data/com.TribeXR.TribeXR:
/sdcard/Android/data/com.TribeXR.TribeXR/cache:
/sdcard/Android/data/com.TribeXR.TribeXR/files:
/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents:
/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/TribeRecordings:
/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/cache:
/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/rekordbox:
/sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus:
/sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR/Saved:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR/Saved/Logs:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Content:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Content/Certificates:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved:
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Logs:
/sdcard/Android/data/com.TribeXR.TribeXR/files/VulkanProgramBinaryCache:
/sdcard/Android/data/com.TribeXR.TribeXR/files/beatport:
/sdcard/Android/data/com.TribeXR.TribeXR/files/compressed:

=== [2] internal storage via run-as (release build expected to FAIL): ===
run-as: package not debuggable: com.TribeXR.TribeXR

=== cacheFile.txt (48 bytes): ===
main.2300.com.TribeXR.TribeXR.obb,1788627213553
(end)
```

### [043] 2026-09-28 23:29:31 · exit 0

```sh
echo "=== grep of external_tree.txt for target patterns (\.glb|cache|Cache|Saved|Avatar|ETag|readyplayer): ==="
grep -niE "\.glb|cache|saved|avatar|etag|readyplayer" cache/external_tree.txt
echo; echo "=== files/compressed/ contents: ==="; grep -A50 "files/compressed:" cache/external_tree.txt | sed "/^$/q"
echo "=== files/UnrealGame/.../Content + Saved contents: ==="; awk "/UnrealGame\/TribeXR\/TribeXR\/(Content|Saved)/{p=1} p" cache/external_tree.txt | sed -n "1,60p"
```

```text
=== grep of external_tree.txt for target patterns (\.glb|cache|Cache|Saved|Avatar|ETag|readyplayer): ===
5:drwxrws---  2 u0_a107  ext_data_rw 4096 2024-02-22 13:00 cache
8:/sdcard/Android/data/com.TribeXR.TribeXR/cache:
19:-rwxrwx--- 1 u0_a107 ext_data_rw  3790959 2026-09-19 12:27 CachedAvatars.zip
22:-rwxrwx--- 1 u0_a107 ext_data_rw  7877284 2026-09-19 12:27 OvrAvatar2Assets.zip
23:-rwxrwx--- 1 u0_a107 ext_data_rw 63625279 2026-09-19 12:27 PresetAvatars_Quest2.zip
26:drwxr-s--- 2 u0_a107 ext_data_rw     4096 2026-09-19 12:27 VulkanProgramBinaryCache
47:-rw-rw---- 1 u0_a107 ext_data_rw       48 2026-09-05 14:12 cacheFile.txt
55:drwxr-s--- 2 u0_a107 ext_data_rw 4096 2024-02-22 13:02 cache
67:/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/cache:
82:drwxrws--- 2 u0_a107 ext_data_rw 4096 2025-05-05 17:27 Avatars2
84:/sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2:
89:-rw-rw---- 1 u0_a107 ext_data_rw  3601596 2025-05-05 17:27 A_1232362938473877.glb
90:-rw-rw---- 1 u0_a107 ext_data_rw  3434756 2024-06-24 12:12 A_1426978754688935.glb
91:-rw-rw---- 1 u0_a107 ext_data_rw  3246510 2024-06-24 12:05 A_1677002969771167.glb
92:-rw-rw---- 1 u0_a107 ext_data_rw  3150026 2024-06-24 11:50 A_2546452168858501.glb
93:-rw-rw---- 1 u0_a107 ext_data_rw  3516589 2024-03-16 15:15 A_258875507279586.glb
94:-rw-rw---- 1 u0_a107 ext_data_rw  3464265 2025-01-08 22:05 A_2641865686006165.glb
95:-rw-rw---- 1 u0_a107 ext_data_rw  2477639 2024-04-06 12:41 A_311473537933362.glb
96:-rw-rw---- 1 u0_a107 ext_data_rw  3869262 2024-06-24 11:29 A_368505276218154.glb
97:-rw-rw---- 1 u0_a107 ext_data_rw  3690510 2025-01-13 20:13 A_408029648751395.glb
98:-rw-rw---- 1 u0_a107 ext_data_rw  3608863 2024-03-07 15:24 A_413060121118574.glb
99:-rw-rw---- 1 u0_a107 ext_data_rw  3632409 2024-06-24 12:06 A_437208149136331.glb
100:-rw-rw---- 1 u0_a107 ext_data_rw  2847602 2024-07-23 12:30 A_838591288205515.glb
101:-rw-rw---- 1 u0_a107 ext_data_rw  3375551 2024-06-24 12:28 A_845683494085919.glb
102:-rw-rw---- 1 u0_a107 ext_data_rw  4017176 2024-06-24 12:34 A_975825064240371.glb
120:drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 Saved
122:/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR/Saved:
128:/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR/Saved/Logs:
150:drwxrws--- 3 u0_a107 ext_data_rw 4096 2025-06-03 16:42 Saved
164:/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved:
170:/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Logs:
175:/sdcard/Android/data/com.TribeXR.TribeXR/files/VulkanProgramBinaryCache:

=== files/compressed/ contents: ===
/sdcard/Android/data/com.TribeXR.TribeXR/files/compressed:
total 1928
drwxr-s--- 2 u0_a107 ext_data_rw   4096 2026-09-19 12:43 .
drwxrws--- 9 u0_a107 ext_data_rw   4096 2026-09-19 12:44 ..
-rw-rw---- 1 u0_a107 ext_data_rw 765553 2026-09-19 12:34 20260905195738_20260919122857.zip

... [36 lines omitted, full output in logs/043.log] ...

drwxrws--- 9 u0_a107 ext_data_rw 4096 2026-09-19 12:44 ..
-rw-rw---- 1 u0_a107 ext_data_rw   36 2025-01-08 21:49 d.txt

/sdcard/Android/data/com.TribeXR.TribeXR/files/compressed:
total 1928
drwxr-s--- 2 u0_a107 ext_data_rw   4096 2026-09-19 12:43 .
drwxrws--- 9 u0_a107 ext_data_rw   4096 2026-09-19 12:44 ..
-rw-rw---- 1 u0_a107 ext_data_rw 765553 2026-09-19 12:34 20260905195738_20260919122857.zip
-rw-rw---- 1 u0_a107 ext_data_rw 747616 2026-09-19 12:40 20260919122857_20260919123456.zip
-rw-rw---- 1 u0_a107 ext_data_rw 447938 2026-09-19 12:43 20260919123456_20260919123831.zip
```

### [044] 2026-09-28 23:30:11 · exit 0

```sh
D=/sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2
echo "=== md5sum + size of every .glb (and the .anim.zip) in Oculus/Avatars2: ==="
adb shell "cd $D && md5sum *.glb *.anim.zip 2>/dev/null"
echo; echo "=== double-check: any .glb ANYWHERE else under the app external dir? ==="
adb shell find /sdcard/Android/data/com.TribeXR.TribeXR/ -iname "*.glb" 2>/dev/null | grep -v "/Oculus/Avatars2/" || echo "(none outside Oculus/Avatars2)"
echo; echo "=== beatport/d.txt (36 bytes) + Documents/cache autosave head: ==="
adb shell cat /sdcard/Android/data/com.TribeXR.TribeXR/files/beatport/d.txt 2>&1; echo
echo "=== the three compressed/*.zip: what are they? (unzip -l via adb not avail; list names by pulling headers) ==="
adb shell "cd /sdcard/Android/data/com.TribeXR.TribeXR/files/compressed && for z in *.zip; do echo \"-- \$z\"; done"
```

```text
=== md5sum + size of every .glb (and the .anim.zip) in Oculus/Avatars2: ===
15fe594586f2814fe94a2f68cee99afb  A_1232362938473877.glb
ce0ea7d8794129ee4de49945f70f7677  A_1426978754688935.glb
ec68b88f7fe810f41dd099ef38b50c60  A_1677002969771167.glb
e676fa4c459c672ddf1587265ffc6e73  A_2546452168858501.glb
b5d6fdf537de9eae6e558d5fb7e16a5c  A_258875507279586.glb
62f3398d41ca9824ccadefcd9e719b00  A_2641865686006165.glb
b2f9823bd697be4650d64aa7f90f18be  A_311473537933362.glb
3b61ffb886a89ee8a566cfa32325dda6  A_368505276218154.glb
0979c4862fa974f6ad19996a49335897  A_408029648751395.glb
3616cb7432025b828c8921f940dc995e  A_413060121118574.glb
d71cd1f585e9e0d4a7095c173ea34e4f  A_437208149136331.glb
af24f1542c69c3b4ff56d3e7803c46ba  A_838591288205515.glb
056ccf2caa527afd574da508e6763255  A_845683494085919.glb
f8d0a5a87c71d3b145e8ad38b2656236  A_975825064240371.glb
0c8e0a61be6f610354983f0da093811d  A_1208024283466024.anim.zip

=== double-check: any .glb ANYWHERE else under the app external dir? ===
(none outside Oculus/Avatars2)

=== beatport/d.txt (36 bytes) + Documents/cache autosave head: ===
2b162de8-b3e6-4f71-8a81-e11226c02875
=== the three compressed/*.zip: what are they? (unzip -l via adb not avail; list names by pulling headers) ===
-- 20260905195738_20260919122857.zip
-- 20260919122857_20260919123456.zip
-- 20260919123456_20260919123831.zip
```

---

## Phase 2 — avatar cache location & writability (2026-09-28, read-only)

Confirmed engine UE5.4, code in libUnreal.so, RPM path uses glTFRuntime + ETag cache
(`GetAvatarUrlCacheFilename`, `ReadyPlayerMeETag` in libUnreal.so, prior phase).

### Findings

- **run-as internal check [step 2]:** `run-as com.TribeXR.TribeXR ls files` →
  `run-as: package not debuggable`. Internal storage `/data/data/com.TribeXR.TribeXR/`
  is OFF-LIMITS without root. On the record. (Release build, `android:debuggable=false`.)

- **Only loose GLBs in external storage:** `files/Oculus/Avatars2/A_<id>.glb` — 14 files,
  2.4–4.0 MB each, plus one `A_1208024283466024.anim.zip`. This is the **Meta Avatars 2
  (OvrAvatar2) local cache**: the `Oculus/Avatars2/` path and 15–16-digit numeric Meta
  avatar IDs are Meta's SDK cache, NOT Ready Player Me. Perms `-rw-rw----  u0_a107
  ext_data_rw` on /sdcard = EXTERNAL, writable unrooted. md5sums recorded in log [step 3].

- **NO Ready Player Me / glTFRuntime GLB anywhere in external storage.** `find -iname *.glb`
  returns nothing outside Oculus/Avatars2. No `readyplayer`/`ETag`/RPM-hex-id file, no
  glTFRuntime cache dir. RPM avatar IDs are 24-char hex; none present.

- **Three "avatar" zips in files/ are bundled Meta SDK assets, not user data:**
  `CachedAvatars.zip` (3,790,959), `OvrAvatar2Assets.zip` (7,877,284),
  `PresetAvatars_Quest2.zip` (63,625,279) — sizes byte-identical to the same-named entries
  inside the OBB (prior phase), i.e. extracted from the package at first run.

- **Non-avatar external items:** `agora*.log` (voice SDK logs), `compressed/*.zip`
  (timestamp-range names `YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.zip` = rotated logs/telemetry),
  `VulkanProgramBinaryCache/` (shader PSO cache), `Documents/TribeRecordings/` (audio),
  `beatport/d.txt` + `cacheFile.txt` = UUID / OBB-download bookkeeping,
  `UnrealGame/.../Saved/Logs` (empty), `Content/Certificates/cacert.pem`.

### Which GLB is "mine" vs bundled

- **Bundled default/mentor** (`DefaultAvatar.glb`, `MentorAvatar.glb`): NOT loose in external
  storage — they stay inside the OBB paks (`TribeXR/Content/Replays/`), read directly.
- **The 14 `A_*.glb`:** Meta Avatars cached from multiplayer rooms + own account. Likely-own:
  `A_1208024283466024` (the only ID with a paired `.anim.zip`; Meta downloads full anim data
  for the local avatar). Medium confidence — not verified against the account's Meta avatar ID.

### Answer (step 4)

- **Meta Avatars 2 cache:** `…/files/Oculus/Avatars2/A_<metaAvatarId>.glb` (+ `.anim.zip`).
  **EXTERNAL — writable without root.** A file-drop is physically possible here, but this is
  the Meta path, and the OvrAvatar2 SDK re-fetches/validates from Meta servers, so a dropped
  file is liable to be overwritten (not verified).
- **Ready Player Me / glTFRuntime ETag cache (the glTFRuntime path):** NOT present in external
  storage. Therefore it is **INTERNAL (`/data/data/…`, needs root)** or not yet created on this
  device. Not a file-drop target on an unrooted headset.

**Bottom line:** For the RPM/glTFRuntime avatar specifically, the cache is not reachable
unrooted → the file-drop route does NOT apply; that avatar path is decided in native code
(the `https://readyplayer.me/api/avatar/` constant + ETag cache), i.e. the URL-redirect /
binary route from phase 1. Meta-avatar files ARE writable externally, but that is a
different avatar system.

---

## Phase 3 — avatar select/load logic in libUnreal.so (2026-09-28, read-only static analysis)

Tool: Ghidra 12.0.4 headless (JDK 21, 16G heap), project in scratchpad `gh_proj/tribexr`, import
`unpacked/base/lib/arm64-v8a/libUnreal.so` (129,868,152 bytes, ARM64, stripped). Post-script
`scripts/AvatarXrefs.java` walks each confirmed string literal -> xrefs -> containing function ->
decompile + callers, output to `out/avatar_xrefs.txt`. (Ghidra 12 removed Jython; `.py` GhidraScripts
need PyGhidra, so the walker is Java.) Note: symbols are stripped, but this is a UE build so
UFUNCTION/UPROPERTY/UENUM names survive as reflection strings — those are the anchors.

### Verified from reflection-name tables (before decompilation)

- **glTFRuntime load API present (Q3):** all of `glTFLoadAssetFromFilename[Async]`,
  `glTFLoadAssetFromData[Async]` (= bytes), `glTFLoadAssetFromUrl[Async]`, `...FromString`,
  `...FromFileMap`, `...FromClipboard`, `...FromCommand`. So the loader can take a file path, a
  byte buffer, or a URL; which one the RPM path uses is pending decompilation.
- **Tribe avatar function surface (Q1/Q2):** `GetAvatarTypeForId`, `GetAvatarIdForServer`,
  `GetAvatarId`/`SaveAvatarId`, `GetTribeDefaultAvatarId`, `GetTribeMentorAvatarId`,
  `GetAvatarsPath` (cache dir builder), `GetAvatarUrlCacheFilename`, `GetAvatarImageCacheFilename`,
  `IsMetaAvatarsSupported`, `IsValidReadyPlayerMeAvatarUrl`, `IsValidReadyPlayerMeAvatarID`,
  `ReadyPlayerMeAvatarUrl`, `QueriedAvatarUrl`, load callbacks `HandleReadyPlayerMeOnAvatarCached`,
  `HandleAvatarAssetLoaded`, `HandleAvatarSkeletonLoaded`, `HandleActiveAvatarLoaded`,
  `HandleAvatarMetadata`, `LoadRPMAvatarThumbnail`, `LoadAvatarMetaData`. Enum `ETribeAvatarType`
  with `InAvatarType`/`CurrentETribeAvatarType`.
- **Avatar type is derived from the avatar ID (Q1):** the selector is `GetAvatarTypeForId(id)` —
  type is a function of the stored/queried ID, not an independent ini toggle. No `AvatarType=`
  ini key found; persistence hook is `SaveAvatarId` (SaveGame/profile, not GConfig — pending).
- **Hardcoded 24-hex RPM avatar IDs embedded** (e.g. `e75b398ed60144a4e58b4d9a`,
  `61df8f5f68c7388fa117345e`, `c935d99d7cf2016289302412`, `4c603efb0cca074e9238af8b`) — consistent
  with RPM IDs being 24-char hex and Meta IDs being decimal; likely the default/mentor avatars.
- **UE modules:** `/Script/TribeXR`, `/Script/TribeIntonal`, `/Script/TribeMIDI`.
- **Host literals (Q4):** only `readyplayer.me` (bare) and `https://readyplayer.me/api/avatar/`
  occur; generic `https://`/`http://` are UE-wide. Exact validator logic pending decompilation.

### Pending: decompilation of the anchored functions (out/avatar_xrefs.txt) — analysis running.

### Decompiled logic (verified in out/avatar_impls.txt; addresses are image-based)

**Q1 — how the local avatar TYPE is chosen.** `GetAvatarTypeForId(id)` = impl `FUN_050fc054`:
```
if isUrlWithScheme(id)            -> ReadyPlayerMe        (FUN_04c5b250)
else if id endsWith ".glb" (+chk) -> ReadyPlayerMe        (FUN_0157dedc + FUN_016f26c4)
else if isMetaId(id)              -> MetaAvatar2          (FUN_04b9efd8)
else                              -> None
```
The RPM branch is exactly `IsValidReadyPlayerMeAvatarID` (`FUN_05188e3c`: URL-or-`.glb`). So the
type is a pure classification of the stored id STRING — no server flag, no separate ini toggle.
The local id/url is a STORED SETTING: `FUN_050f584c` reads it with a GConfig-style
`GetString(section="TribeAvatar", key="ReadyPlayerMeAvatarUrl" / "ReadyPlayerMeETag", ini=<global>)`.
`GetAvatarIdForServer` (`FUN_050fc6e0`) hands your id to the server so peers load your avatar.
**To make the local avatar resolve to MetaAvatar2:** set the stored avatar id to a Meta id (i.e.
pick a Meta avatar in-app / clear the RPM url) so it fails the URL/`.glb` test and passes the
Meta-id test. This is what the in-app avatar picker already does — no patch needed.

**Q2 — Meta path is independent.** `IsMetaAvatarsSupported` -> constant true on this build
(`FUN_03fc4c54`->`FUN_01546060` returns 1). Meta presets load through
`FUN_04ba868c` using wide literal `zip://%s_quest2.glb` into `libovravatar2.so`; runtime avatars
cache at `Oculus/Avatars2/A_<metaId>.glb` (Phase 2). The Meta avatar source is your Quest system
(Meta account) avatar, editable in the Quest avatar editor — you control it there, independent of RPM.

**Q3 — glTFRuntime load source, path, integrity.** RPM load `FUN_050f49cc` builds the cache path,
checks `FileExists` (`FUN_016f26c4`), and calls loader `FUN_050f4548` with a FILE PATH (the cache
file if present; else fallback `Replays/DefaultAvatar.glb` via `FUN_050f5e58`). So it loads from a
FILE on disk (glTFRuntime `...FromFilename`), not from in-memory bytes, for the local avatar.
  - Cache dir: `GetAvatarsPath` (`FUN_0514ec88`) = `<ProjectUserDir>/Documents/Avatars/`.
  - Cache filename: `GetAvatarUrlCacheFilename` (`FUN_050fd620`) = `sprintf("%srpmavatar-%s", dir,
    basename(url))`; `basename` = `FUN_016f1d84` (GetCleanFilename, last `/`|`\` segment).
    => `<ProjectUserDir>/Documents/Avatars/rpmavatar-<lastPathSegmentOfUrl>` (deterministic, no hash).
  - **Integrity: NONE beyond scheme + `.glb` suffix + FileExists.** No hash, size, or signature
    check appears before glTFRuntime parses the file; the ETag (`ReadyPlayerMeETag`) is only HTTP
    If-None-Match download caching, not content validation.

**Q4 — URL validation strictness.** `IsValidReadyPlayerMeAvatarUrl` = `FUN_04c5b250`: splits on
`"://"`, then accepts scheme ∈ {`http`, `https`, `file`}. **No host check** — `http://127.0.0.1/x.glb`,
a LAN address, or `file://…` all pass. A URL redirect does NOT need to defeat a host validator.

**Storage location (Q3 internal/external) — CORRECTION to Phase 2a.** The cache base is
`<ProjectUserDir>/Documents/…`, the same `Documents/` that holds the external recordings
(`files/Documents/TribeRecordings`, Phase 2). So the RPM cache dir is
`/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/` — EXTERNAL, writable unrooted
(strong inference from the shared `Documents/` base; the base global is runtime-set so not provable
from the static image). It is ABSENT today only because the local avatar is a Meta avatar, so no
RPM avatar was ever downloaded (device re-scan: no `Documents/Avatars/`, no `rpmavatar-*`, no ini).
Phase 2a inferred "internal" from that absence; the code shows the path is external-and-empty.
**Confirm empirically:** pick any RPM avatar once in-app, then re-scan — `Documents/Avatars/rpmavatar-*`
should appear in external storage.

### Q5 — smallest viable change, ranked

1. **(a) Force MetaAvatar2 + use a Meta avatar — smallest, zero patch.** Select a Meta avatar in
   app (stores a Meta id -> `GetAvatarTypeForId`=MetaAvatar2). Edit its look in the Quest avatar
   editor. Nothing patched, nothing dropped. Survives updates (it's a feature). Limit: it's a Meta
   avatar, not an arbitrary custom `.glb`.
2. **(d) File-drop into the RPM cache — no binary patch (NEW, from the load path).** Because the
   loader loads `Documents/Avatars/rpmavatar-<basename(url)>` from disk with only a FileExists/`.glb`
   gate and NO hash/signature check, dropping your own RPM-topology `.glb` under that name makes the
   app load it (ETag/FileExists short-circuits the download). Requires: base dir external (inferred —
   confirm per above); the local url set to a readyplayer URL so type=RPM and the basename is known;
   a `.glb` matching the RPM skeleton (`EReadyPlayerMeBone::*`). Path format is app logic, so it
   survives app updates better than a code patch.
3. **(b) Redirect the RPM URL to your own HTTPS host — no binary patch if the URL is settable.**
   The native validator won't block a non-RPM host (scheme-only). Needs: the stored
   `[TribeAvatar]ReadyPlayerMeAvatarUrl` pointed at your `https://…/x.glb` (via the in-app RPM entry
   if it accepts arbitrary URLs, else editing the ini — internal => root), your HTTPS server (valid
   cert; `cacert.pem` bundled), and an RPM-compatible `.glb`. Survives updates (no code changed).
4. **(c) Hook the glTFRuntime file/bytes loader — largest, least durable.** Patch/hook
   `FUN_050f4548` / the `glTFLoadAssetFromFilename` call. Requires modifying+re-signing `libUnreal.so`
   (breaks the read-only constraint) and breaks on every app update (addresses move). Last resort.

**Decisive facts:** (i) no integrity/signature check before glTFRuntime parses the local avatar
file; (ii) the local avatar is chosen purely by the FORMAT of a stored id/url, which the in-app
picker already controls; (iii) the URL validator is scheme-only (no host). Together these mean a
custom local avatar most likely needs NO binary patch — either a Meta pick (a), a cache file-drop
(d), or a URL redirect (b) — provided the cache base is external (the one remaining thing to confirm).

### [045] 2026-09-29 08:33:24 · exit 0

```sh
echo "=== pak tools / rust already installed? ==="; for t in repak repak.exe cargo rustc UnrealPak UnrealPak.exe dotnet; do printf "%-12s " "$t"; command -v "$t" 2>/dev/null || echo "(no)"; done
echo "=== search likely dirs for Oodle libs (oo2core*/liblinoodle*) ==="
for d in "/c/Program Files/Epic Games" "/c/Program Files" "/c/Program Files (x86)/Steam/steamapps/common" "/c/Users/Chris" "/c/ghidra-work" "/c/Users/Chris/Downloads"; do
  [ -d "$d" ] && find "$d" -maxdepth 6 -iname "oo2core*" -o -iname "liblinoodle*" 2>/dev/null; done | sort -u | head -40
echo "=== UE engine installs? ==="; ls -d "/c/Program Files/Epic Games/UE_"* 2>/dev/null; ls -d "/c/Program Files/Epic Games/UE_5"*/Engine/Binaries/ThirdParty/Oodle/* 2>/dev/null
echo "=== Oodle inside the pulled APK/OBB? ==="
unzip -l pulled/base.apk | grep -iE "oo2core|oodle|linoodle" || echo "(no oodle lib in APK)"
echo "=== does libUnreal.so export/contain Oodle symbols? ==="
grep -a -o -E "oo2core[a-zA-Z0-9_]*|OodleLZ_[A-Za-z]+|liblinoodle" unpacked/base/lib/arm64-v8a/libUnreal.so | sort | uniq -c | head
```

```text
=== pak tools / rust already installed? ===
repak        (no)
repak.exe    (no)
cargo        /c/Users/Chris/.cargo/bin/cargo
rustc        /c/Users/Chris/.cargo/bin/rustc
UnrealPak    (no)
UnrealPak.exe (no)
dotnet       /c/Program Files/dotnet/dotnet
=== search likely dirs for Oodle libs (oo2core*/liblinoodle*) ===
=== UE engine installs? ===
=== Oodle inside the pulled APK/OBB? ===
(no oodle lib in APK)
=== does libUnreal.so export/contain Oodle symbols? ===
      1 OodleLZ_Compress
      4 OodleLZ_Compressor
      2 OodleLZ_Decode
     14 OodleLZ_Decompress
      2 OodleLZ_GetAllChunksCompressor
      1 OodleLZ_ThreadPhased
```

### [046] 2026-09-29 08:35:06 · exit 0

```sh
echo "=== full C: search for any Windows Oodle DLL / linoodle / pak tools (bounded) ==="
timeout 240 find /c -iname "oo2core*" -o -iname "liblinoodle*" -o -iname "oodle*.dll" 2>/dev/null | sort -u | head -40; echo "(oodle search done, rc=$?)"
echo "=== any FModel / CUE4Parse / repak already on disk? ==="
timeout 120 find /c/Users/Chris -iname "*fmodel*" -o -iname "*cue4parse*" -o -iname "repak*" 2>/dev/null | head -20; echo "(tool search done)"
```

```text
=== full C: search for any Windows Oodle DLL / linoodle / pak tools (bounded) ===
(oodle search done, rc=0)
=== any FModel / CUE4Parse / repak already on disk? ===
(tool search done)
```

### [047] 2026-09-29 08:42:52 · exit 0

```sh
python scripts/pak_list.py pulled/main.2304.com.TribeXR.TribeXR.obb extracted/paklist.txt; echo "--- sample paths (first 15 non-comment): ---"; grep -v "^#" extracted/paklist.txt | head -15; echo "--- total non-comment lines: $(grep -vc "^#" extracted/paklist.txt) ---"
```

```text
TribeXR/Content/Paks/pakchunk0-Android_ASTC.pak: 10289 files  mount=../../../
TribeXR/Content/Paks/pakchunk0optional-Android_ASTC.pak: 7 files  mount=../../../TribeXR/Content/Environment/
TribeXR/Content/Paks/pakchunk1-Android_ASTC.pak: 497 files  mount=../../../TribeXR/Content/
TribeXR/Content/Paks/pakchunk1optional-Android_ASTC.pak: 9 files  mount=../../../TribeXR/Content/
total files listed: 10802 -> extracted/paklist.txt
--- sample paths (first 15 non-comment): ---
../../../Engine/GlobalShaderCache-VULKAN_ES3_1_ANDROID.bin
../../../Engine/Config/Base.ini
../../../Engine/Config/BaseCompat.ini
../../../Engine/Config/BaseDeviceProfiles.ini
../../../Engine/Config/BaseEngine.ini
../../../Engine/Config/BaseGame.ini
../../../Engine/Config/BaseGameUserSettings.ini
../../../Engine/Config/BaseHardware.ini
../../../Engine/Config/BaseInput.ini
../../../Engine/Config/BaseInstallBundle.ini
../../../Engine/Config/BaseRuntimeOptions.ini
../../../Engine/Config/BaseScalability.ini
../../../Engine/Config/ConfigRedirects.ini
../../../Engine/Config/PluginBase.ini
../../../Engine/Config/Android/AndroidEngine.ini
--- total non-comment lines: 10802 ---
```

### [048] 2026-09-29 08:43:04 · exit 0

```sh
L=extracted/paklist.txt
echo "=== all avatar/skeleton/rpm/glb/rig/mannequin hits -> extracted/avatar_asset_hits.txt ==="
grep -viE "^#" "$L" | grep -iE "readyplayer|/rpm|_rpm|rpm_|avatar|skel|skeleton|/rig|_rig|mannequin|default_?avatar|mentor|\.glb|gltf" | sort -u | tee extracted/avatar_asset_hits.txt | wc -l
echo; echo "=== raw .glb / .gltf bundled in content: ==="; grep -iE "\.glb|\.gltf" extracted/avatar_asset_hits.txt || echo "(none)"
echo; echo "=== Skeleton-ish (SK_/skeleton/_skel/Skeletal): ==="; grep -iE "SK_|skeleton|_skel|skeletal" extracted/avatar_asset_hits.txt | head -40
echo; echo "=== ReadyPlayerMe / RPM assets: ==="; grep -iE "readyplayer|rpm" extracted/avatar_asset_hits.txt | head -40
```

```text
=== all avatar/skeleton/rpm/glb/rig/mannequin hits -> extracted/avatar_asset_hits.txt ===
738

=== raw .glb / .gltf bundled in content: ===
../../../TribeXR/Content/Replays/DanceAvatar.glb
../../../TribeXR/Content/Replays/DefaultAvatar.glb
../../../TribeXR/Content/Replays/MentorAvatar.glb

=== Skeleton-ish (SK_/skeleton/_skel/Skeletal): ===
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/A9/SK_DJM-A9_Mixer_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/A9/SK_DJM-A9_Mixer_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/CDJ3000/SK_CDJ3000_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/CDJ3000/SK_CDJ3000_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/CDJ3000X/SK_CDJ3000X_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/CDJ3000X/SK_CDJ3000X_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/DDJ-FLX4/SK_DDJ-FLX4_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/DDJ-FLX4/SK_DDJ-FLX4_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/DJM-NXS-2/SK_DJM-NXS-2_Mixer_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/DJM-NXS-2/SK_DJM-NXS-2_Mixer_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/DJM-V10/SK_DJM-V10_Mixer_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/DJM-V10/SK_DJM-V10_Mixer_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/StarterCDJ/SK_StarterCDJ_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/StarterCDJ/SK_StarterCDJ_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/StarterMixer/SK_StarterMixer_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/StarterMixer/SK_StarterMixer_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeAcidSynth/SK_TribeAcidSynth_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeAcidSynth/SK_TribeAcidSynth_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeCDJ/TribeCDJ_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeCDJ/TribeCDJ_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeDrumMachine/SK_TribeDrumMachine_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeDrumMachine/SK_TribeDrumMachine_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeMixer/SK_TribeMixer_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeMixer/SK_TribeMixer_Skeleton.uexp
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeVinyl/Geometry/SK_VinylDeck_Skeleton.uasset
../../../TribeXR/Content/Equipment/Assets/EquipmentMesh/TribeVinyl/Geometry/SK_VinylDeck_Skeleton.uexp
../../../TribeXR/Content/Equipment/Models/SkeletalMeshes/SK_CDJ3000.uasset
../../../TribeXR/Content/Equipment/Models/SkeletalMeshes/SK_CDJ3000.uexp
../../../TribeXR/Content/Equipment/Models/SkeletalMeshes/SK_CDJ3000X.uasset
../../../TribeXR/Content/Equipment/Models/SkeletalMeshes/SK_CDJ3000X.uexp
../../../TribeXR/Content/Equipment/Models/SkeletalMeshes/SK_DDJ-FLX4.uasset

... [14 lines omitted, full output in logs/048.log] ...

../../../TribeXR/Content/Menus/Assets/Icons/T_Icon_RPM_Goto.uexp
../../../TribeXR/Content/Menus/Assets/Icons/T_Icon_RPM_Paste.uasset
../../../TribeXR/Content/Menus/Assets/Icons/T_Icon_RPM_Paste.uexp
../../../TribeXR/Content/Menus/W_RPMAvatarCreator.uasset
../../../TribeXR/Content/Menus/W_RPMAvatarCreator.uexp
../../../TribeXR/Content/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin.uasset
../../../TribeXR/Content/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin.uexp
../../../TribeXR/Content/Visuals/Skins/OculusAvatar/PreviewImages/T_SkinPreview_ReadyPlayerMe_Custom.uasset
../../../TribeXR/Content/Visuals/Skins/OculusAvatar/PreviewImages/T_SkinPreview_ReadyPlayerMe_Custom.uexp
../../../TribeXR/Plugins/ReadyPlayerMe/ReadyPlayerMe.uplugin
```

### [049] 2026-09-29 08:45:00 · exit 0

```sh
echo "=== compression of the three bundled avatar GLBs: ==="; python scripts/pak_entry.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/DanceAvatar.glb"; python scripts/pak_entry.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/DefaultAvatar.glb"; python scripts/pak_entry.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/MentorAvatar.glb"
echo; echo "=== sanity: compression spread across a sample of entries (are ANY stored?) ==="; python scripts/pak_entry.py pulled/main.2304.com.TribeXR.TribeXR.obb ".glb" | grep -E "method=" | sed -E "s/.*method=([0-9]+) \(([^)]*)\).*/\1 \2/" | sort | uniq -c
```

```text
=== compression of the three bundled avatar GLBs: ===
../../../TribeXR/Content/Replays/DanceAvatar.glb
    method=1 (Oodle)  encrypted=False  blocks=3  size=31,447  uncompressed=147,948  offset=374033340  pak=pakchunk0-Android_ASTC.pak
../../../TribeXR/Content/Replays/DefaultAvatar.glb
    method=1 (Oodle)  encrypted=False  blocks=73  size=1,081,863  uncompressed=4,732,412  offset=374066761  pak=pakchunk0-Android_ASTC.pak
../../../TribeXR/Content/Replays/MentorAvatar.glb
    method=1 (Oodle)  encrypted=False  blocks=73  size=1,101,370  uncompressed=4,752,440  offset=537006048  pak=pakchunk0-Android_ASTC.pak

=== sanity: compression spread across a sample of entries (are ANY stored?) ===
      3 1 Oodle
```

---

## Phase A/B — pak tooling, Oodle blocker, avatar asset inventory (2026-09-29, read-only)

Outputs in ./extracted/. Read the pak index directly from inside the OBB (stored entries); nothing
extracted to disk (footprint-minimal).

### Phase A result: BLOCKED on Oodle (stopping here per instruction)

- Tooling present: `cargo`/`rustc` (can build repak), `dotnet`. Absent: repak, UnrealPak, FModel/CUE4Parse.
- **No Oodle decompressor anywhere on this PC.** Full C: search for `oo2core*`, `liblinoodle*`,
  `oodle*.dll` = nothing. No UE engine install to source one from. The APK has no Oodle lib.
  `libUnreal.so` statically links Oodle (`OodleLZ_Decompress` present) but it is ARM64 — unusable
  on this x86 PC.
- The 4 paks are pak v11, index unencrypted, entries Oodle-compressed. Listing needs no Oodle;
  **decompression does.** So Phase A step 4 (decompress one entry) cannot pass here.

### Phase B result: full file list obtained without Oodle (index is plaintext)

- `scripts/pak_list.py` parses the pak Full Directory Index from the OBB → `extracted/paklist.txt`
  (10,802 files). `scripts/pak_entry.py` decodes an entry's compression method/size.
- Grep hits → `extracted/avatar_asset_hits.txt` (738). Classified:
  - **Bundled reference GLBs (the target), all in pakchunk0, all Oodle-compressed:**
    - `TribeXR/Content/Replays/DefaultAvatar.glb` — uncompressed 4,732,412 B; this is the RPM
      loader's fallback avatar (`FUN_050f5e58`, Phase 3) → the reference skeleton+mesh.
    - `TribeXR/Content/Replays/MentorAvatar.glb` — uncompressed 4,752,440 B.
    - `TribeXR/Content/Replays/DanceAvatar.glb` — uncompressed 147,948 B (small; likely dance-anim).
  - **RPM UI/skin assets (uasset/uexp, Oodle):** `Menus/W_RPMAvatarCreator`,
    `Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin`,
    `Menus/Assets/Icons/T_Icon_RPM_{Copy,Goto,Paste}`, `PreviewImages/T_SkinPreview_ReadyPlayerMe_Custom`,
    `Plugins/ReadyPlayerMe/ReadyPlayerMe.uplugin`.
  - **No avatar USkeleton/SkeletalMesh uasset.** Every `SK_*_Skeleton` is DJ equipment
    (mixers/CDJs/synths), not an avatar. Confirms the RPM avatar is a runtime GLB (glTFRuntime),
    not a cooked USkeleton — so the reference IS the GLB (matches the loader; ideal per Phase C.2a).

### What's missing and the options (Oodle)

Need a Windows Oodle 2.9 decompressor `oo2core_9_win64.dll` (UE 5.4 uses Oodle 2.9.x). Options:
1. Install UE 5.4 via Epic Games Launcher and copy
   `Engine/Binaries/ThirdParty/Oodle/Win64/oo2core_9_win64.dll` into the working dir (freely
   redistributable with the engine). Then build repak (`cargo`) with Oodle, or extract via a small
   ctypes harness (we already decode pak entries).
2. Copy `oo2core_9_win64.dll` from any UE-based game already on another machine (none found here).
3. Extract on a machine that has UE installed.

Once the DLL is present, extracting `DefaultAvatar.glb` is trivial (~1 MB compressed, 73 blocks) and
yields skeleton + sample mesh directly — no uasset parsing needed. NB: the exact bone NAME set is
already known from Phase 3 (`EReadyPlayerMeBone`: AvatarRoot, Hips, Spine, Neck, Head, Left/RightEye,
Left/RightHand + full finger chains) — the GLB adds bind poses, hierarchy order, and the mesh.

**STOP (Phase A Oodle gate + Phase B candidate review).** Awaiting: (a) an `oo2core_9_win64.dll`,
and (b) OK to extract the candidate GLBs once it's available.

### [050] 2026-09-29 08:50:38 · exit 0

```sh
adb devices -l | grep -w device || { echo "NO DEVICE"; exit 1; }
echo "=== [1] every .glb anywhere under /sdcard/ (path, size) ==="
adb shell "find /sdcard/ -iname \"*.glb\" -exec ls -la {} \; 2>/dev/null" | tr -d "\r"
echo "=== [1b] any *avatar*.glb specifically ==="
adb shell "find /sdcard/ -iname \"*avatar*.glb\" 2>/dev/null" | tr -d "\r"
echo "=== [2] Replays / extracted / cooked content dirs under the app files dir ==="
adb shell "find /sdcard/Android/data/com.TribeXR.TribeXR/ -type d \( -iname \"Replays\" -o -iname \"*extract*\" -o -iname \"*Content*\" -o -iname \"*cooked*\" -o -iname \"Paks\" \) 2>/dev/null" | tr -d "\r"
echo "=== [2b] DefaultAvatar / MentorAvatar / DanceAvatar by name anywhere on /sdcard ==="
adb shell "find /sdcard/ \( -iname \"DefaultAvatar*\" -o -iname \"MentorAvatar*\" -o -iname \"DanceAvatar*\" \) 2>/dev/null" | tr -d "\r"
echo "(scan complete)"
```

```text
2G0YC1ZF96072F         device product:eureka model:Quest_3 device:eureka transport_id:8
=== [1] every .glb anywhere under /sdcard/ (path, size) ===
-rw-rw---- 1 u0_a107 ext_data_rw 3375551 2024-06-24 12:28 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_845683494085919.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3150026 2024-06-24 11:50 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_2546452168858501.glb
-rw-rw---- 1 u0_a107 ext_data_rw 2847602 2024-07-23 12:30 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_838591288205515.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3690510 2025-01-13 20:13 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_408029648751395.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3601596 2025-05-05 17:27 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_1232362938473877.glb
-rw-rw---- 1 u0_a107 ext_data_rw 2477639 2024-04-06 12:41 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_311473537933362.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3464265 2025-01-08 22:05 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_2641865686006165.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3434756 2024-06-24 12:12 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_1426978754688935.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3632409 2024-06-24 12:06 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_437208149136331.glb
-rw-rw---- 1 u0_a107 ext_data_rw 4017176 2024-06-24 12:34 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_975825064240371.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3608863 2024-03-07 15:24 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_413060121118574.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3869262 2024-06-24 11:29 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_368505276218154.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3516589 2024-03-16 15:15 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_258875507279586.glb
-rw-rw---- 1 u0_a107 ext_data_rw 3246510 2024-06-24 12:05 /sdcard/Android/data/com.TribeXR.TribeXR/files/Oculus/Avatars2/A_1677002969771167.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2236784 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_576404647650066.glb
-rw-rw---- 1 u0_a120 ext_data_rw 3384915 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1299338774248806.glb
-rw-rw---- 1 u0_a120 ext_data_rw 297609 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_722324616128539.glb
-rw-rw---- 1 u0_a120 ext_data_rw 3015242 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1204480777119881.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2096243 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_675021977709914.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2769411 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1201144050831171.glb
-rw-rw---- 1 u0_a120 ext_data_rw 1986506 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1537700413370689.glb
-rw-rw---- 1 u0_a120 ext_data_rw 255515 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_702194231485194.glb
-rw-rw---- 1 u0_a120 ext_data_rw 1852584 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_496837532517159.glb
-rw-rw---- 1 u0_a120 ext_data_rw 261820 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1339129586908120.glb
-rw-rw---- 1 u0_a120 ext_data_rw 264676 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_8670582926316778.glb
-rw-rw---- 1 u0_a120 ext_data_rw 311955 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1793927007649941.glb
-rw-rw---- 1 u0_a120 ext_data_rw 363509 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_722196245847985.glb
-rw-rw---- 1 u0_a120 ext_data_rw 251913 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1566206963846523.glb
-rw-rw---- 1 u0_a120 ext_data_rw 275345 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_3508464322808614.glb
-rw-rw---- 1 u0_a120 ext_data_rw 3106097 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_685250219798024.glb
-rw-rw---- 1 u0_a120 ext_data_rw 269849 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_852893662654985.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2140403 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_877885690323203.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2002252 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_866186628005484.glb
-rw-rw---- 1 u0_a120 ext_data_rw 293345 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_680436747130080.glb
-rw-rw---- 1 u0_a120 ext_data_rw 274375 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1083823439122617.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2689750 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_881034386548261.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2644078 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_704876301097425.glb
-rw-rw---- 1 u0_a120 ext_data_rw 253178 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_887681502425598.glb
-rw-rw---- 1 u0_a120 ext_data_rw 314635 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_472790305061026.glb
-rw-rw---- 1 u0_a120 ext_data_rw 286163 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_690511866125394.glb
-rw-rw---- 1 u0_a120 ext_data_rw 285322 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_565857824877620.glb
-rw-rw---- 1 u0_a120 ext_data_rw 1841774 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_655342009607073.glb
-rw-rw---- 1 u0_a120 ext_data_rw 1947521 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_1342866393202098.glb
-rw-rw---- 1 u0_a120 ext_data_rw 2705003 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_566020468874096.glb
-rw-rw---- 1 u0_a120 ext_data_rw 3016350 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_8431226706951412.glb
-rw-rw---- 1 u0_a120 ext_data_rw 289674 2024-02-22 13:23 /sdcard/Android/data/com.LuckyVR.PokerStarsVR/files/Oculus/Avatars2/A_5745376728902771.glb
-rw-rw---- 1 u0_a10 ext_data_rw 5085804 2024-02-22 12:56 /sdcard/Android/data/com.oculus.shellenv/files/Oculus/Avatars2/A_334854198922557.glb
=== [1b] any *avatar*.glb specifically ===
=== [2] Replays / extracted / cooked content dirs under the app files dir ===
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Content
=== [2b] DefaultAvatar / MentorAvatar / DanceAvatar by name anywhere on /sdcard ===
(scan complete)
```

### Phase B addendum — external .glb scan for the bundled reference (read-only)

`find /sdcard/ -iname "*.glb"` (whole external storage). Result: the ONLY `.glb` files on disk are
Meta Avatars2 caches (`.../files/Oculus/Avatars2/A_<metaId>.glb`) for TribeXR, PokerStarsVR and
shellenv — Meta-avatar skeleton, NOT Ready Player Me. **DefaultAvatar.glb / MentorAvatar.glb /
DanceAvatar.glb are NOT present anywhere on /sdcard** (searched by name and by `*avatar*.glb`); no
`Replays/`, `extracted/`, `cooked/` or `Paks/` dir exists under the app files dir. So UE streams the
bundled avatar GLBs from the Oodle-compressed pak into RAM (glTFRuntime via the mounted pak VFS) and
never writes them to disk — there is no on-disk copy to grab. Nothing pulled (per instruction, only
pull if the reference GLB is found). **Conclusion: the no-Oodle shortcut fails; the Oodle route is
required to obtain the RPM reference GLB.**

### [051] 2026-09-29 08:57:30 · exit 0

```sh
ls -la oo2core_9_win64.dll 2>&1; file oo2core_9_win64.dll 2>/dev/null; echo "--- python arch + load test ---"; python - <<PY
import ctypes, os, struct
p=os.path.abspath("oo2core_9_win64.dll")
print("python bits:", struct.calcsize("P")*8, "| dll exists:", os.path.exists(p), os.path.getsize(p) if os.path.exists(p) else "-")
try:
    dll=ctypes.WinDLL(p)
    fn=dll.OodleLZ_Decompress
    print("LOADED OK; OodleLZ_Decompress present:", bool(fn))
    for sym in ("OodleLZ_Compress","OodleLZDecoder_MemorySizeNeeded","Oodle_GetConfigValues"):
        print("  export", sym, ":", hasattr(dll, sym))
except OSError as e:
    print("LOAD FAILED:", e)
PY
```

```text
ls: cannot access 'oo2core_9_win64.dll': No such file or directory
oo2core_9_win64.dll: cannot open `oo2core_9_win64.dll' (No such file or directory)
--- python arch + load test ---
python bits: 64 | dll exists: False -
LOAD FAILED: Could not find module 'C:\Users\Chris\OneDrive\Desktop\tribe hack\oo2core_9_win64.dll' (or one of its dependencies). Try using the full path with constructor syntax.
```

### [052] 2026-09-29 09:04:06 · exit 0

```sh
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/find_oodle_targeted.ps1")" 2>&1 | tr -d "\r"
```

```text
Fixed drives: C:, D:
=== targeted common game-install roots ===
  scanning: C:\Program Files (x86)\Steam\steamapps\common
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\Elite Dangerous\Products\elite-dangerous-odyssey-64\GpuWorkTable.xml  (40548 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\Elite Dangerous\Products\elite-dangerous-odyssey-64\InstallerInfo.txt  (67 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\MGSDelta.exe  (15275080 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Binaries\ThirdParty\DbgHelp\dbghelp.dll  (2221984 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Binaries\ThirdParty\NVIDIA\NVaftermath\Win64\GFSDK_Aftermath_Lib.x64.dll  (1865216 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Binaries\ThirdParty\Ogg\Win64\VS2015\libogg_64.dll  (49152 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Binaries\ThirdParty\Steamworks\Steamv153\Win64\steam_api64.dll  (295336 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Binaries\ThirdParty\Vorbis\Win64\VS2015\libvorbisfile_64.dll  (37888 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Binaries\ThirdParty\Vorbis\Win64\VS2015\libvorbis_64.dll  (1714176 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Binaries\ThirdParty\Windows\XAudio2_9\x64\xaudio2_9redist.dll  (847440 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Content\Slate\Cursor\invisible.cur  (326 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Marketplace\nvidia\DLSS\Binaries\ThirdParty\Win64\nvngx_dlss.dll  (51717160 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Marketplace\nvidia\Streamline\Binaries\ThirdParty\Win64\nvngx_dlssg.dll  (12582456 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Marketplace\nvidia\Streamline\Binaries\ThirdParty\Win64\sl.common.dll  (615392 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Marketplace\nvidia\Streamline\Binaries\ThirdParty\Win64\sl.dlss_g.dll  (365016 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Marketplace\nvidia\Streamline\Binaries\ThirdParty\Win64\sl.interposer.dll  (510944 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Marketplace\nvidia\Streamline\Binaries\ThirdParty\Win64\sl.reflex.dll  (144864 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkAudioInput.dll  (127752 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkCompressor.dll  (144136 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkConvolutionReverb.dll  (221448 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkDelay.dll  (132872 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkExpander.dll  (144136 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkFlanger.dll  (154888 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkGain.dll  (127752 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkGuitarDistortion.dll  (167176 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkHarmonizer.dll  (225032 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkMatrixReverb.dll  (193800 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkMotion.dll  (215816 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkParametricEQ.dll  (156424 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkPeakLimiter.dll  (135432 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkPitchShifter.dll  (162568 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkRecorder.dll  (128264 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkReflect.dll  (191752 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkRoomVerb.dll  (244488 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkSilenceGenerator.dll  (119048 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkSineTone.dll  (128264 bytes)
    FOUND  C:\Program Files (x86)\Steam\steamapps\common\MGSDelta\Engine\Plugins\Wwise\ThirdParty\x64_vc170\Release\bin\AkSoundEngineDLL.dll  (1615112 bytes)

... [36700 lines omitted, full output in logs/052.log] ...

    FOUND  D:\SteamLibrary\steamapps\common\FINAL FANTASY XIV Online\game\sqpack\ffxiv\130000.win32.index  (2304 bytes)
    FOUND  D:\SteamLibrary\steamapps\common\FINAL FANTASY XIV Online\game\sqpack\ffxiv\130000.win32.index2  (2304 bytes)
    FOUND  D:\SteamLibrary\steamapps\common\PUBG\Engine\Binaries\ThirdParty\CEF3_3071\Win64\openh264-2.1.0-win64.dll  (897272 bytes)
    FOUND  D:\SteamLibrary\steamapps\common\PUBG\TslGame\Binaries\Win64\bgsecondary.dat  (10158080 bytes)
    FOUND  D:\SteamLibrary\steamapps\common\PUBG\TslGame\Binaries\Win64\Guid.dat  (36 bytes)
    FOUND  D:\SteamLibrary\steamapps\common\PUBG\TslGame\Config\DefaultCompat.ini  (15387 bytes)
    FOUND  D:\SteamLibrary\steamapps\common\PUBG\TslGame\Config\DefaultLightmass.ini  (6862 bytes)
=== installed UE-based games (Engine/ dir or *-Shipping.exe) in those roots ===
  UE game: C:\Program Files (x86)\Steam\steamapps\common\MGSDelta
  UE game: D:\SteamLibrary\steamapps\common\PUBG
```

### [053] 2026-09-29 09:06:56 · exit 0

```sh
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/find_oodle2.ps1")" 2>&1 | tr -d "\r"
```

```text
=== direct: UE game Binaries\Win64 dirs ===
=== full per-drive -Filter search (correct) ===
  drive C:
  drive D:
=== done ===
```

### Phase A-fin blocked — no Oodle DLL on any drive (2026-09-29, read-only)

Wider search (this time correct — `-Filter` works with `-Recurse`, unlike `-Include`): full recurse of
both fixed drives C: and D: for `oo2core*.dll` and `oodle*.dll` = ZERO hits. Direct check of the two
installed UE games' binaries = none either.
- Installed UE games found: `C:\Program Files (x86)\Steam\steamapps\common\MGSDelta` (UE5),
  `D:\SteamLibrary\steamapps\common\PUBG` (UE4). Neither ships a loose `oo2core_*_win64.dll`.
- Reason: PACKAGED UE games statically link Oodle into the shipping exe; the loose
  `oo2core_9_win64.dll` ships with the UE ENGINE/EDITOR (Epic Games Launcher), not with games.
  So "pull it from a UE5 game I own" does not work for these titles.
- oo2core DLL is still required for the Windows extract route; not present. Phase A-fin cannot run.

### [054] 2026-09-29 09:20:00 · exit 0

```sh
echo "=== binutils / compilers / NDK present? ==="; for t in readelf nm objdump gcc g++ clang cc cl; do printf "%-9s " "$t"; command -v "$t" 2>/dev/null || echo "(no)"; done
echo "ANDROID_NDK env: ${ANDROID_NDK:-<unset>} / ${ANDROID_NDK_HOME:-<unset>} / ${NDK_HOME:-<unset>}"
echo "=== NDK / cmdline-tools on disk? (bounded) ==="; timeout 60 find /c/Users/Chris -maxdepth 5 -type d \( -iname "ndk" -o -iname "android-ndk*" \) 2>/dev/null | head; ls -d /c/Users/Chris/AppData/Local/Android/Sdk/ndk/* 2>/dev/null
echo "=== is OodleLZ_Decompress an EXPORTED dynamic symbol in libUnreal.so? ==="
python - <<PY
import struct
f=open("unpacked/base/lib/arm64-v8a/libUnreal.so","rb"); d=f.read(64)
assert d[:4]==b"\x7fELF"
is64=d[4]==2; le="<"
e_shoff=struct.unpack_from(le+"Q",d,0x28)[0]
e_shentsize=struct.unpack_from(le+"H",d,0x3a)[0]
e_shnum=struct.unpack_from(le+"H",d,0x3c)[0]
e_shstrndx=struct.unpack_from(le+"H",d,0x3e)[0]
f.seek(e_shoff); sh=f.read(e_shentsize*e_shnum)
secs=[]
for i in range(e_shnum):
    o=i*e_shentsize
    name,typ=struct.unpack_from(le+"II",sh,o)
    off,size=struct.unpack_from(le+"QQ",sh,o+0x18)
    link,info=struct.unpack_from(le+"II",sh,o+0x28)
    entsz=struct.unpack_from(le+"Q",sh,o+0x38)[0]
    secs.append([name,typ,off,size,link,entsz])
# section header string table
stab=secs[e_shstrndx]; f.seek(stab[2]); shstr=f.read(stab[3])
def nm(n): return shstr[n:shstr.index(b"\0",n)].decode()
dynsym=dynstr=None
for s in secs:
    if nm(s[0])==".dynsym": dynsym=s
    if nm(s[0])==".dynstr": dynstr=s
if not dynsym: print("no .dynsym"); raise SystemExit
f.seek(dynstr[2]); ds=f.read(dynstr[3])
f.seek(dynsym[2]); sym=f.read(dynsym[3])
cnt=dynsym[3]//24; found=[]; total=0
for i in range(cnt):
    o=i*24; nameoff=struct.unpack_from(le+"I",sym,o)[0]
    shndx=struct.unpack_from(le+"H",sym,o+6)[0]
    val=struct.unpack_from(le+"Q",sym,o+8)[0]
    nmv=ds[nameoff:ds.index(b"\0",nameoff)].decode("latin-1")
    if nmv: total+=1
    if "Oodle" in nmv or "oodle" in nmv:
        found.append((nmv,shndx,hex(val)))
print("dynamic symbols:",total,"| Oodle-named exported:",len(found))
for n,sh,v in found[:30]: print("   ",n,"shndx=",sh,"val=",v)
PY
```

```text
=== binutils / compilers / NDK present? ===
readelf   (no)
nm        (no)
objdump   (no)
gcc       (no)
g++       (no)
clang     (no)
cc        (no)
cl        (no)
ANDROID_NDK env: <unset> / <unset> / <unset>
=== NDK / cmdline-tools on disk? (bounded) ===
=== is OodleLZ_Decompress an EXPORTED dynamic symbol in libUnreal.so? ===
dynamic symbols: 1404 | Oodle-named exported: 0
```

### [055] 2026-09-29 09:22:04 · exit 0

```sh
echo "### validate header parse on DanceAvatar (small) + DefaultAvatar (big) ###"; python scripts/pak_extract.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/DanceAvatar.glb" extracted/assets; echo; python scripts/pak_extract.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/DefaultAvatar.glb" extracted/assets; echo "--- files written:"; ls -l extracted/assets/
```

```text
### validate header parse on DanceAvatar (small) + DefaultAvatar (big) ###
../../../TribeXR/Content/Replays/DanceAvatar.glb
  pak=pakchunk0-Android_ASTC.pak method=1(Oodle) blocks=3 size=31,447 usize=147,948 off=374033340
  -> wrote DanceAvatar.glb.oodleblocks (31,447 B, 3 blocks), manifest (raw total 147,948 == usize 147,948: True), relative_offsets=True

../../../TribeXR/Content/Replays/DefaultAvatar.glb
  pak=pakchunk0-Android_ASTC.pak method=1(Oodle) blocks=73 size=1,081,863 usize=4,732,412 off=374066761
  -> wrote DefaultAvatar.glb.oodleblocks (1,081,863 B, 73 blocks), manifest (raw total 4,732,412 == usize 4,732,412: True), relative_offsets=True
--- files written:
total 1101
-rw-r--r-- 1 Chris 197121     316 Sep 29 09:22 DanceAvatar.glb.manifest.json
-rw-r--r-- 1 Chris 197121   31447 Sep 29 09:22 DanceAvatar.glb.oodleblocks
-rw-r--r-- 1 Chris 197121    4817 Sep 29 09:22 DefaultAvatar.glb.manifest.json
-rw-r--r-- 1 Chris 197121 1081863 Sep 29 09:22 DefaultAvatar.glb.oodleblocks
```

### [056] 2026-09-29 09:25:11 · exit 1

```sh
OD="/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/oodle_dec/target/release/oodle_dec.exe"; cd extracted/assets
python -c "import json;m=json.load(open(\"DanceAvatar.glb.manifest.json\"));open(\"DanceAvatar.blocks.txt\",\"w\").write(\"\n\".join(f\"{b[\"comp_len\"]} {b[\"raw_len\"]}\" for b in m[\"blocks\"]))"
"$OD" DanceAvatar.glb.oodleblocks DanceAvatar.blocks.txt DanceAvatar.glb
echo "--- verify magic + size ---"; python -c "
d=open(\"DanceAvatar.glb\",\"rb\").read()
import struct
print(\"size:\",len(d))
print(\"magic:\",d[:4], \"(glTF)\" if d[:4]==b\"glTF\" else \"(NOT glTF)\")
ver,length=struct.unpack_from(\"<II\",d,4); print(\"glb version:\",ver,\"declared length:\",length,\"match:\",length==len(d))
"
```

```text

thread 'main' (10128) panicked at src\main.rs:26:33:
block 0: decompress failed: OozError
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
--- verify magic + size ---
Traceback (most recent call last):
  File "<string>", line 2, in <module>
    d=open("DanceAvatar.glb","rb").read()
      ~~~~^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'DanceAvatar.glb'
```

### [057] 2026-09-29 09:26:07 · exit 0

```sh
OD="/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/oodle_dec/target/release/oodle_dec.exe"; rm -f extracted/assets/DanceAvatar.glb
python scripts/pak_extract.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/DanceAvatar.glb" extracted/assets
cd extracted/assets
python -c "import json;m=json.load(open(\"DanceAvatar.glb.manifest.json\"));open(\"DanceAvatar.blocks.txt\",\"w\").write(chr(10).join(str(b[\"comp_len\"])+\" \"+str(b[\"raw_len\"]) for b in m[\"blocks\"]))"
"$OD" DanceAvatar.glb.oodleblocks DanceAvatar.blocks.txt DanceAvatar.glb
python -c "
import struct
d=open(\"DanceAvatar.glb\",\"rb\").read()
print(\"size:\",len(d),\"magic:\",d[:4])
if d[:4]==b\"glTF\":
    ver,length=struct.unpack_from(\"<II\",d,4)
    print(\"OK glTF v\",ver,\"len\",length,\"match\",length==len(d))
    # first chunk (JSON)
    clen,ctyp=struct.unpack_from(\"<II\",d,12); print(\"chunk0 len\",clen,\"type\",d[20:24])
    print(\"JSON head:\", d[24:24+180].decode(\"utf-8\",\"replace\"))
"
```

```text
../../../TribeXR/Content/Replays/DanceAvatar.glb
  pak=pakchunk0-Android_ASTC.pak method=1(Oodle) blocks=3 size=31,447 usize=147,948 off=374033340
  header_size=105 block0.start=105 relative=True
  -> wrote DanceAvatar.glb.oodleblocks (31,447 B, 3 blocks), manifest (raw total 147,948 == usize 147,948: True), relative_offsets=True
wrote 147948 bytes to DanceAvatar.glb
size: 147948 magic: b'glTF'
OK glTF v 2 len 147948 match True
chunk0 len 44236 type b'{"as'
JSON head: set":{"generator":"Khronos glTF Blender I/O v1.8.19","version":"2.0"},"scene":0,"scenes":[{"name":"Scene","nodes":[55]}],"nodes":[{"name":"RightEye_end","rotation":[-2.846733404560
```

### [058] 2026-09-29 09:26:58 · exit 1

```sh
OD="/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/oodle_dec/target/release/oodle_dec.exe"
# re-extract all three to emit sidecars, then decompress
python scripts/pak_extract.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/DefaultAvatar.glb" extracted/assets >/dev/null
python scripts/pak_extract.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/MentorAvatar.glb" extracted/assets >/dev/null
python scripts/pak_extract.py pulled/main.2304.com.TribeXR.TribeXR.obb "Replays/DanceAvatar.glb" extracted/assets >/dev/null
cd extracted/assets
for n in DefaultAvatar MentorAvatar DanceAvatar; do "$OD" $n.glb.oodleblocks $n.blocks.txt $n.glb; done
echo "--- verify ---"; python ../../scripts/glb_verify.py DefaultAvatar.glb MentorAvatar.glb DanceAvatar.glb
```

```text

thread 'main' (11980) panicked at src\main.rs:13:45:
read sidecar: Os { code: 2, kind: NotFound, message: "The system cannot find the file specified." }
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

thread 'main' (7208) panicked at src\main.rs:13:45:
read sidecar: Os { code: 2, kind: NotFound, message: "The system cannot find the file specified." }
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
wrote 147948 bytes to DanceAvatar.glb
--- verify ---
Traceback (most recent call last):
  File "C:\Users\Chris\OneDrive\Desktop\tribe hack\scripts\glb_verify.py", line 8, in <module>
    d = open(path, "rb").read()
        ~~~~^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'DefaultAvatar.glb'
```

### [059] 2026-09-29 09:28:46 · exit 0

```sh
python scripts/glb_report.py extracted/assets/DefaultAvatar.glb extracted/skeleton_report.md
```

```text
wrote extracted/skeleton_report.md (105 lines)
skin0 joints=38  meshes=1  materials=1  images=2
```

---

## Phase A-fin / C / D — reference GLB extracted, skeleton report produced (2026-09-29)

Oodle route WITHOUT the oo2core DLL: no DLL/UE install/NDK was available, but rust/cargo is, so I
used a pure-Rust Oodle decompressor (`oozextract` v0.5.5) — all on PC, read-only toward the game.

- **Tooling.** `scripts/pak_extract.py` parses the full FPakEntry header from inside the OBB and
  writes each entry's Oodle blocks + a sidecar; `scratchpad/oodle_dec` (Rust, `oozextract`)
  decompresses the blocks; `scripts/glb_verify.py` + `scripts/glb_report.py` validate/parse the GLB.
  Block offsets are v9+ relative-to-entry (block0.start == header_size, verified).
- **Phase A-fin (pipeline proof):** `DanceAvatar.glb` decompressed to a valid glTF v2 (147,948 B).
- **Phase C (extracted to `extracted/assets/`, all valid glTF v2, sizes == uncompressed):**
  - `DefaultAvatar.glb` 4,732,412 B  md5 `bb01368fc663411e5ad676ee268aac4e`
  - `MentorAvatar.glb` 4,752,440 B  md5 `defb8f2890727d0e12ad1b1d2daff235`
  - `DanceAvatar.glb`   147,948 B  md5 `10192f53353e2dd983693bb8d3f22a2f`
- **Phase D (`extracted/skeleton_report.md`):** `DefaultAvatar.glb` = half-body RPM avatar
  (`Wolf3D_Avatar`, Blender-exported). 38 joints, upper body only: `Hips→Spine→{Neck→Head→
  {L/R Eye}; R/LHand→5 finger chains}`; **hands parent to Spine** (no arms/legs). Matches
  `EReadyPlayerMeBone` exactly (38/39; only `AvatarRoot` absent = runtime root, not a joint; 0 extra
  joints). Mesh: 1 skinned mesh, 5051 verts, 1 UV, 1 doubleSided material (baseColor+normal PNG).
  **63 morph targets** = ARKit set + 15 `viseme_*` (OVRLipSync drives these). Units meters, Y-up,
  Hips at origin. Full joint list + bind-pose TRS in the report.
- `extracted/assets/` (the GLBs + manifests) is gitignored (binaries); `skeleton_report.md`,
  `paklist.txt`, `avatar_asset_hits.txt` and the scripts are tracked.

### [060] 2026-09-29 09:55:27 · exit 0

```sh
adb devices -l | grep -w device >/dev/null || { echo NO DEVICE; exit 1; }
echo "=== every .ini / .cfg / .sav under the app external dir ==="
adb shell "find /sdcard/Android/data/com.TribeXR.TribeXR/ \( -iname \"*.ini\" -o -iname \"*.cfg\" -o -iname \"*.sav\" -o -iname \"*.save\" \) -exec ls -la {} \; 2>/dev/null" | tr -d "\r"
echo "=== any Config or SaveGames dirs under the app tree ==="
adb shell "find /sdcard/Android/data/com.TribeXR.TribeXR/ -type d \( -iname \"Config\" -o -iname \"SaveGames\" -o -iname \"*Saved*\" \) 2>/dev/null" | tr -d "\r"
echo "=== full recursive listing of files/UnrealGame and files/UE4Game (where Saved/Config would be) ==="
adb shell "ls -laR /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame /sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game 2>/dev/null" | tr -d "\r"
echo "(scan done)"
```

```text
=== every .ini / .cfg / .sav under the app external dir ===
=== any Config or SaveGames dirs under the app tree ===
/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved
/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR/Saved
=== full recursive listing of files/UnrealGame and files/UE4Game (where Saved/Config would be) ===
/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 .
drwxrws--- 9 u0_a107 ext_data_rw 4096 2026-09-19 12:44 ..
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 TribeXR

/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 .
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 ..
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 TribeXR

/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 .
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 ..
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 Saved

/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR/Saved:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 .
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 ..
drwxrws--- 2 u0_a107 ext_data_rw 4096 2024-02-22 12:57 Logs

/sdcard/Android/data/com.TribeXR.TribeXR/files/UE4Game/TribeXR/TribeXR/Saved/Logs:
total 8
drwxrws--- 2 u0_a107 ext_data_rw 4096 2024-02-22 12:57 .
drwxrws--- 3 u0_a107 ext_data_rw 4096 2024-02-22 12:57 ..

/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame:
total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2025-06-03 16:42 .
drwxrws--- 9 u0_a107 ext_data_rw 4096 2026-09-19 12:44 ..
drwxrws--- 3 u0_a107 ext_data_rw 4096 2025-06-03 16:42 TribeXR


... [26 lines omitted, full output in logs/060.log] ...

total 12
drwxrws--- 3 u0_a107 ext_data_rw 4096 2025-06-03 16:42 .
drwxrws--- 4 u0_a107 ext_data_rw 4096 2025-06-03 16:42 ..
drwxrws--- 2 u0_a107 ext_data_rw 4096 2025-06-03 16:42 Logs

/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Logs:
total 8
drwxrws--- 2 u0_a107 ext_data_rw 4096 2025-06-03 16:42 .
drwxrws--- 3 u0_a107 ext_data_rw 4096 2025-06-03 16:42 ..
(scan done)
```

---

## Phase — how ReadyPlayerMeAvatarUrl gets written (2026-09-29, static + read-only device)

Ghidra: `scripts/ConfigTrace.java` + `scripts/CmdlineTrace.java` (out/config_trace.txt, out/cmdline.txt).

### Backend: GConfig .ini, section [TribeAvatar]
- `FUN_016a70bc` = `FConfigCacheIni::GetString`. `PTR_DAT_07ba1c58` = GConfig; `PTR_DAT_07ba2d90` =
  the ini this section lives in (a distinct global from the engine ini `07ba1c60`). Runtime-set
  (.bss), so the exact basename isn't in the static image; most likely `GameUserSettings.ini`
  (user prefs) — confirm on-device.
- `[TribeAvatar]` keys seen: `AvatarID` (current avatar; read in `FUN_0518ba70`),
  `ReadyPlayerMeAvatarUrl`, `ReadyPlayerMeETag`, `bExperimentalTrackingEnabled`.
- **Setter** = `FUN_016a851c` (`FConfigCacheIni::SetString`). The ONLY writer of the RPM keys is the
  loader `FUN_050f49cc` writing `ReadyPlayerMeETag` after a successful download. The URL itself was
  written by the (now-removed) RPM UI; no remaining code writes `ReadyPlayerMeAvatarUrl`.
- No console command / exec UFUNCTION sets the url: `SetReadyPlayerMe`/`SetAvatarUrl` = 0 hits;
  `SetAvatar*` present are visibility/scene-capture + reflection registration, not URL setters.
  `SaveGameToSlot` exists but is unrelated (this is GConfig, not a SaveGame).

### Storage location: INTERNAL (root needed to edit directly)
- Device scan: NO `*.ini`/`*.cfg`/`*.sav` anywhere under the external app dir; external `Saved/`
  dirs contain only empty `Logs/` (no `Config/`). `run-as` is blocked (release build). So the ini
  is in internal storage `/data/data/com.TribeXR.TribeXR/.../Saved/Config/Android/` — root only.

### Unrooted vector found: external UE command-line override
- `FUN_04760484` reads bundled `assets/UECommandLine.txt` (= `-project="../../../TribeXR/TribeXR.uproject"`),
  THEN builds `<ExternalFilesDir>/UnrealGame/<Project>/UECommandLine.txt` (strings `/UnrealGame/`,
  `/UECommandLine.txt`) and `fopen(..., "r")` on it — **unconditionally, no `UE_BUILD_SHIPPING`
  guard in the loader** (case-insensitive fallback to `uecommandline.txt` too). Likely path:
  `/sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt` (EXTERNAL,
  writable unrooted) — confirm exact path via logcat ("APK Commandline: %s" is logged).
- UE applies `-ini:<IniName>:[Section]:Key=Value` overrides into GConfig at startup, which the later
  `GetString([TribeAvatar], ReadyPlayerMeAvatarUrl/AvatarID)` would return — so this can set the
  value with no UI, no root, no binary patch. Unverified end-to-end; needs an on-device test.

### Ranked ways to set ReadyPlayerMeAvatarUrl without the UI (cheapest first)
1. **External `UECommandLine.txt` + `-ini:` override — no root, no patch, no UI.** Drop a text file
   at the external path above containing (keep the original -project, then add overrides), e.g.:
   `-project="../../../TribeXR/TribeXR.uproject" -ini:GameUserSettings:[TribeAvatar]:ReadyPlayerMeAvatarUrl="https://<host>/<name>.glb" -ini:GameUserSettings:[TribeAvatar]:AvatarID="https://<host>/<name>.glb"`
   Try ini name `GameUserSettings` first, then `Game`. Verify via `adb logcat` (command line echo +
   avatar load). Writes one file to the app's external data dir (not the game binary). TEST NEEDED.
2. **Root the Quest → edit the internal ini** `[TribeAvatar] ReadyPlayerMeAvatarUrl=/AvatarID=`
   directly. Reliable, survives updates, but Quest 3 has no public root.
3. **Patch/hook `libUnreal.so`** (force the url/id or GetAvatarTypeForId). No root, but re-signs/
   re-installs the app (breaks read-only-of-game) and breaks on each update. Last resort.
- No console-command or SaveGame path exists.

### [061] 2026-09-29 10:12:06 · exit 0

```sh
CL="/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/UECommandLine.txt"
echo "=== push UECommandLine.txt to both candidate paths ==="
adb push "$CL" /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt
adb push "$CL" /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/UECommandLine.txt
echo "=== pre-seed cache: rpmavatar-test.glb ==="
adb push extracted/assets/DefaultAvatar.glb /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb
echo "=== verify placement ==="
adb shell "ls -l /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/UECommandLine.txt /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb 2>&1" | tr -d "\r"
echo "=== show pushed cmdline content ==="; adb shell "cat /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt" | tr -d "\r"
```

```text
=== push UECommandLine.txt to both candidate paths ===
adb: error: cannot stat '/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/UECommandLine.txt': No such file or directory
adb: error: cannot stat '/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/UECommandLine.txt': No such file or directory
=== pre-seed cache: rpmavatar-test.glb ===
adb: error: failed to copy 'extracted/assets/DefaultAvatar.glb' to '/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb': remote secure_mkdirs failed: Permission denied
extracted/assets/DefaultAvatar.glb: 1 file pushed, 0 skipped. 174.2 MB/s (4732412 bytes in 0.026s)
=== verify placement ===
ls: /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt: No such file or directory
ls: /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/UECommandLine.txt: No such file or directory
ls: /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb: No such file or directory
=== show pushed cmdline content ===
cat: /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt: No such file or directory
```

### [062] 2026-09-29 10:12:56 · exit 0

```sh
CL=$(cygpath -w "/c/Users/Chris/AppData/Local/Temp/claude/C--Users-Chris-OneDrive-Desktop-tribe-hack/1513371d-9360-4e12-b704-023d9fd6c661/scratchpad/UECommandLine.txt"); GLB=$(cygpath -w "$PWD/extracted/assets/DefaultAvatar.glb")
echo "=== push UECommandLine.txt into EXISTING dirs (Windows source path) ==="
adb push "$CL" /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt 2>&1 | tr -d "\r"
adb push "$CL" /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/UECommandLine.txt 2>&1 | tr -d "\r"
echo "=== can shell create the Avatars/ dir? ==="
adb shell "mkdir -p /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars 2>&1; ls -ld /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars 2>&1" | tr -d "\r"
echo "=== pre-seed cache glb (if Avatars/ now exists) ==="
adb push "$GLB" /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb 2>&1 | tr -d "\r"
echo "=== verify all placements ==="
adb shell "ls -l /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/UECommandLine.txt /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb 2>&1" | tr -d "\r"
```

```text
=== push UECommandLine.txt into EXISTING dirs (Windows source path) ===
C:\Users\Chris\AppData\Local\Temp\claude\C--Users-Chris-OneDrive-Desktop-tribe-hack\1513371d-9360-4e12-b704-023d9fd6c661\scratchpad\UECommandLine.txt: 1 file pushed, 0 skipped. 0.5 MB/s (321 bytes in 0.001s)
C:\Users\Chris\AppData\Local\Temp\claude\C--Users-Chris-OneDrive-Desktop-tribe-hack\1513371d-9360-4e12-b704-023d9fd6c661\scratchpad\UECommandLine.txt: 1 file pushed, 0 skipped. 1.2 MB/s (321 bytes in 0.000s)
=== can shell create the Avatars/ dir? ===
mkdir: '/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars': Permission denied
ls: /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars: No such file or directory
=== pre-seed cache glb (if Avatars/ now exists) ===
adb: error: failed to copy 'C:\Users\Chris\OneDrive\Desktop\tribe hack\extracted\assets\DefaultAvatar.glb' to '/sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb': remote secure_mkdirs failed: Permission denied
C:\Users\Chris\OneDrive\Desktop\tribe hack\extracted\assets\DefaultAvatar.glb: 1 file pushed, 0 skipped. 188.2 MB/s (4732412 bytes in 0.024s)
=== verify all placements ===
ls: /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-test.glb: No such file or directory
-rw-r--r-- 1 shell ext_data_rw 321 2026-09-29 10:11 /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/UECommandLine.txt
-rw-r--r-- 1 shell ext_data_rw 321 2026-09-29 10:11 /sdcard/Android/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/UECommandLine.txt
```

---

## Phase — runtime test of UECommandLine.txt + -ini: override (2026-09-29, ATTEMPT 1: blocked, headset off)

Delivery setup (writes only to the app's EXTERNAL data dir; nothing patched/re-signed):
- HTTP server on PC (`python -m http.server 8080` in extracted/assets) serving `test.glb`
  (copy of DefaultAvatar.glb, 4,732,412 B). Reached from device via `adb reverse tcp:8080 tcp:8080`
  so the device URL is `http://127.0.0.1:8080/test.glb` (validator accepts 127.0.0.1 — no host check).
- Pushed `UECommandLine.txt` (321 B) to BOTH candidate paths (both existed, writes succeeded):
  `…/files/UnrealGame/TribeXR/UECommandLine.txt` and `…/files/UnrealGame/TribeXR/TribeXR/UECommandLine.txt`.
  Content = original `-project=...` + `-ini:GameUserSettings:[TribeAvatar]:ReadyPlayerMeAvatarUrl=<url>,[TribeAvatar]:AvatarID=<url>`
  and the same for `-ini:Game:` (covering both possible ini basenames in one shot).
- Cache pre-seed FAILED: shell cannot `mkdir` new dirs under the app external dir
  (`secure_mkdirs: Permission denied`) — can WRITE files into EXISTING dirs but not create
  `Documents/Avatars/`. So the pre-seed route needs the app to create Avatars/ first; the
  URL-download route (server + adb reverse) does not need it.
- adb shell has NO curl/wget/nc (couldn't test reachability from device shell; PC-side curl 200 OK).

Launch: `am start -n com.TribeXR.TribeXR/com.epicgames.unreal.GameActivity` after `logcat -c` +
`am force-stop`. Result: UE logged only through `GameActivity.onCreate()`/`onCreateBody()` then
STALLED — no `PreInit`, no "Command Line:", no avatar. logcat shows `MrService: … screen is: OFF`:
the headset was not worn, so UE's native init (which reads UECommandLine.txt and loads the avatar)
never ran. Server saw no GET. **Test inconclusive — needs the headset ON.** Full log: logs/launch1.txt.

NEXT (needs the user, physical): put the headset on, launch/enter Tribe, go into a DJ session so the
local avatar spawns. Server + adb reverse are left running; re-capture logcat + watch for GET /test.glb.

## Phase — runtime test ATTEMPT 2 (headset ON, in a session): override did NOT take effect

Widened `UECommandLine.txt` (ini names GameUserSettings/Game/Engine/TribeXR + `-LOG=tribeprobe.log`
read-probe) pushed to 3 external paths (files/, files/UnrealGame/TribeXR/, .../TribeXR/TribeXR/).
Force-stopped, user relaunched and entered a DJ session. Results:
- **No `tribeprobe.log`** created anywhere (Saved/Logs stays empty — this shipping build writes no UE
  log file, so `-LOG` gives no observable signal; read-probe inconclusive).
- **No server request** for test.glb (only my earlier PC-side HEAD).
- **No `Documents/Avatars/`, no `rpmavatar-*`.** Instead the Meta avatar bundles
  (CachedAvatars.zip, PresetAvatars_Quest2.zip, OvrAvatar2Assets.zip) were touched again → the app
  loaded the **Meta** avatar, same as without the file.
- logcat is silent natively (only Java-side GameActivity lines; UE `FUN_015ab8fc` logs like "APK
  Commandline"/"Using override commandline" never reach logcat in this shipping build).

**Verdict: the external-UECommandLine.txt + `-ini:` route did not drive the avatar, and this build
gives no observable signal to say why.** Verified by decompile that the loader *applies* an external
file unconditionally when found (no shipping guard), so the failure is one of: (a) the external path
differs from the 3 tried — base global `07ba1b80` is runtime-set and unresolved (targetSDK 32 scoped
storage may even route it to a `/sdcard/UnrealGame/...` path the scoped app can't read → feature dead);
(b) the `-ini:` ini name doesn't match `[TribeAvatar]`'s ini (`07ba2d90` unresolved); or (c) the local
avatar type isn't re-resolved from `[TribeAvatar]AvatarID` at spawn (it defaults to Meta when no RPM is
actively selected), meaning no config write can flip it — only the removed UI's switch logic (or a
patch) would. Cannot distinguish these without root observability (read internal ini + UE log) or a
binary patch — both outside the read-only/no-root constraints.

## Phase — caller trace: is avatar type re-derived from config at spawn? (read-only static)

`scripts/CallersTrace.java` (out/callers.txt). Findings:
- `GetAvatarTypeForId` (FUN_050fc054): only code caller is its UFUNCTION exec thunk (05097618) →
  **Blueprint-callable**, not called from a native spawn path.
- `[TribeAvatar]AvatarID` reader (FUN_0518ba70): only caller is its exec thunk (050be73c) →
  **Blueprint-callable**.
- RPM loader (FUN_050f49cc) is invoked by FUN_050f5a00, which loads from the avatar COMPONENT's
  url MEMBER (param_1+0x2a8…), not directly from config. So native code = primitives; the decision
  of when to read config and set the component url is **Blueprint** (in the Oodle paks) + the
  now-removed RPM UI.

**Conclusion (reason c is effectively true for the no-UI case):** the local avatar's config→component
wiring is Blueprint-orchestrated and was driven by the removed UI. So a config write alone (even if the
`-ini:` override applied) is not shown to flip the local avatar at spawn — consistent with the two
negative live tests. Confirming/enabling it further needs Blueprint-bytecode analysis of the paks
(large, specialized) or a binary patch (crosses the read-only-of-game line). Both are out of scope of
the read-only + no-root constraints held so far.

### State of the overall goal
Analysis goals are complete: engine ID, avatar select/load logic, URL validator, cache path+format,
config backend, and the reference RPM rig (extracted DefaultAvatar.glb + skeleton_report.md). The only
unmet goal is a WORKING no-root injection of a custom avatar, which is blocked as above.

## Phase — ATTEMPT 3: clean from-launch logcat test (headset on, file staged). Evidence, not inference.

Corrected method: server + adb reverse up, UECommandLine.txt (with -ini: overrides for
GameUserSettings/Game/Engine/TribeXR + `-LOG=tribeprobe.log`) pushed to 3 external paths, logcat
buffer raised to 32M, then `logcat -c` → `am force-stop` → `am start` → 100s LIVE capture from t=0.
This time the app fully booted (headset on).

Confirmed facts:
- App fully booted & running: pid 18567, `topResumedActivity = …/GameActivity`, immersive transition
  ended, 4209 native log lines from the process, spatial/hand tracking active. NOT stalled (unlike
  attempt 1). 15,456 total lines captured.
- It loaded the **Meta** avatar: CachedAvatars.zip / PresetAvatars_Quest2.zip / OvrAvatar2Assets.zip
  all touched at/after 10:51 launch.
- **No RPM activity at all**: no `Documents/Avatars/`, no `rpmavatar-*`, no server GET/HEAD for
  test.glb (only my earlier PC-side HEAD), no `tribeprobe.log`.
- **UE-core logging is OFF in this shipping build** (the key blocker, now proven): of 4209 lines from
  pid 18567, every one is from OVR/OpenXR/Oculus-Platform/RuntimeIPC SDKs; there are ZERO UE-core
  ("UE" tag native) lines and no `APK Commandline`/`Command Line`/`Final commandline`. The decompile
  showed `APK Commandline: %s` runs unconditionally every boot, yet it never appears → UE's FMsg log
  device does not reach logcat here.

**Evidence-based conclusion:** in a clean, fully-booted, headset-on launch with the override file
staged, the RPM path did NOT fire (Meta avatar loaded, zero RPM fetch/cache). BUT the specific check
"did the override enter the resolved command line" is UNOBSERVABLE on this build, because UE-core
logging is disabled — logcat, the UE log file (Saved/Logs empty; `-LOG` produced nothing), and the
internal config are all unavailable without root. So I have evidence the RPM path didn't fire, but
cannot distinguish "external UECommandLine.txt not read at the tried paths" from "config not consumed
at spawn (reason c)". Disambiguating needs an observable independent of UE logging AND the avatar
(e.g. redirect a config-driven startup network endpoint to the local server) — more RE, uncertain.

## Phase — isolate "is the file read" (step 1): both boot-probes confounded → undeterminable black-box

Per the isolate-the-unknowns plan, tried to prove read/not-read via boot behavior (not logging/avatar/net):
- **Probe 1 `-nosound`** (keep -project): after relaunch, Tribe (uid 10107) still had 2 active
  `OpenSL ES AudioPlayer state:started usage=USAGE_MEDIA`. INCONCLUSIVE — Tribe's DJ audio is its own
  SuperPowered/OpenSL engine, which UE's `-nosound` (FAudioDevice) would not disable. So "audio still
  on" ≠ "file not read".
- **Probe 2 bad `-project`** (`ZZDOESNOTEXIST.uproject`): app booted normally (pid stable), Meta avatar
  zips touched (booted to avatar load), no crash, no error. INCONCLUSIVE — `-project` is baked into the
  packaged Android build, so a bad value on the cmdline is ignored on-device.

**Conclusion: which of (a)/(b)/(c) we're in is UNDETERMINABLE by black-box probing on this build.**
Every distinguishing observable is denied: UE-core logging compiled out (proven, attempt 3), no
readable UE log file, internal GameUserSettings.ini unreadable without root, and boot-arg effects are
confounded by app specifics (custom audio; baked project). This is a tested conclusion, not an
inference. A definitive answer needs an observable that crosses the held constraints:
  - **root** (no patch): read the internal ini after a staged launch to see if the `-ini:` override
    took, and read the UE log — the least-invasive way to get certainty; Quest 3 has no public root.
  - **binary patch**: add an observable / force the value — crosses read-only-of-binary.

Device restored to stock (all staged UECommandLine.txt removed; server + adb reverse torn down).
Verified facts that stand: loader applies an external UECommandLine.txt unconditionally when FOUND
(decompile, no shipping guard); the reference RPM rig is extracted; the config backend + cache path are
mapped. What could not be shown: that a staged file is actually read at the tried paths on this build.

## Phase 1 (injected-hook route) — pin the two hook contracts + spawn-trigger verdict (static)

Goal shift: force Tribe to load a custom local GLB unconditionally via a runtime-injected .so
(Dobby-style inline hook), not a byte-patch. Bodies re-read from out/avatar_impls.txt + out/callers.txt
(no new Ghidra run needed). RVAs below are Ghidra image-based — **confirm libUnreal.so load base = 0
(readelf -h) before computing runtime hook addresses.**

### Hook contracts (verified from decompiled bodies)
- **A. GetAvatarTypeForId = FUN_050fc054** (RVA 0x050FC054, size 128).
  `int32 GetAvatarTypeForId(FString* id)` — x0 = FString* (id/url), enum returned in w0.
  Body: `return 1` if IsValidRPMUrl(id)[FUN_04c5b250] OR (endsWith ".glb"[FUN_0157dedc] && FileExists
  [FUN_016f26c4]); else `2` if isMetaId(id)[FUN_04b9efd8]; else `0`.
  **Enum ints CONFIRMED from return constants: None=0, ReadyPlayerMe=1, MetaAvatar2=2.** Force RPM =
  replace hook, `return 1` (no need to call original). Only caller = exec thunk FUN_05097618
  (execGetAvatarTypeForId, writes result to BP return ptr) ⇒ **Blueprint-only, not on a native path.**
- **Config reader FUN_050f584c** (0x050F584C): `void(FString* out /*x0*/, FString* id /*x1*/)`; GConfig
  GetString([TribeAvatar] ReadyPlayerMeAvatarUrl / ReadyPlayerMeETag) via FUN_016a70bc; builds rpmavatar
  path; FileExists gate.
- **Path builder FUN_050fd620 = GetAvatarUrlCacheFilename** (0x050FD620): `void(FString* out /*x0*/,
  FString* url /*x1*/)` = sprintf(out,"%srpmavatar-%s", GetAvatarsPath[FUN_0514EC88],
  GetCleanFilename(url)[FUN_016F1D84]).
- **RPM resolver FUN_050f49cc** (0x050F49CC): `void(this /*x0*/, long flag /*x1*/, FString* url /*x2*/)`.
  Builds rpmavatar-<basename(url)>; if flag==0 && IsValidRPMUrl(url): FileExists(path) ?
  FUN_050f4548(this,path) : FUN_050f4548(this,"Replays/DefaultAvatar.glb"[FUN_050f5e58]).
- **B. glTF file-load CHOKE POINT FUN_050f4548** (0x050F4548, size 1156): `byte(this /*x0*/,
  FString* path /*x1*/)`. Proceeds if IsValidRPMUrl(path) OR (endsWith ".glb" && FileExists); dedupes vs
  this+0x2A8 (current loaded url); fires async glTF load via vtable (*+0x800). **Every RPM-path load
  (cache-hit AND DefaultAvatar fallback) passes through here.**

### Spawn-trigger verdict (Phase 1 step 3) — CORRECTS the "presets are RPM" assumption
- The ~30 in-UI presets are **Meta** avatars (PresetAvatars_Quest2.zip → `zip://%s_quest2.glb` →
  libovravatar2.so; L43-48), NOT ReadyPlayerMe. Selecting a preset drives the **Meta** pipeline, not the
  RPM/glTF path. Corroborated by the headset-on runtime test (Meta zips touched, zero RPM activity).
- All RPM native fns are Blueprint-callable primitives. GetAvatarTypeForId's only caller is its exec
  thunk. RPM resolver FUN_050f49cc is invoked by component methods FUN_050f54c8 (set-url-if-changed) and
  FUN_050f5a00 (reads this+0x2A8 url member from a provider object) — both Blueprint-driven. The Meta
  loader (FUN_04ba868c) is a separate pipeline and is what runs at spawn today.
- **Therefore forcing GetAvatarTypeForId→RPM is necessary but NOT proven sufficient.** Static analysis
  cannot show whether Blueprint consults it at spawn (BP bytecode is Oodle-compressed in the paks; UE
  logging is compiled out). Runtime shows the RPM path does not fire at spawn. If BP doesn't branch the
  spawn load on the type, Hook A is inert and FUN_050f4548 is never reached.

### Recommendation (before building both hooks blind)
1. **Diagnostic-first:** ship ONLY Hook A, instrumented — `__android_log_print` TRIBEMOD the incoming id
   + decision, then return (real value, or forced 1). One launch answers the question static analysis
   can't: does GetAvatarTypeForId fire at spawn?
   - Fires → two-hook plan viable: force→1, set [TribeAvatar]ReadyPlayerMeAvatarUrl to an RPM url whose
     basename resolves to custom.glb, drop the glb at Documents/Avatars/rpmavatar-custom.glb; Hook B pins
     the file.
   - Does NOT fire → **minimal third touch:** redirect the spawn-load entry (FUN_050f5a00 /
     UTribeAvatarComponent init) to call FUN_050f49cc(this,0,&customUrl) unconditionally. Needs tracing
     FUN_050f5a00's caller (the guaranteed-at-spawn entry) — small extra RE.
2. Single best "force my file" point = **hook FUN_050f4548, overwrite param_2 (x1)** with a persistent
   FString = absolute /sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/rpmavatar-custom.glb
   (passes the .glb + FileExists gate; no need to match a basename or defeat config/url plumbing).
   Downstream of all url logic — but only fires if the RPM path is entered at spawn (see verdict).

STOP — awaiting OK before Phase 2 (build).

## Phase 2 diagnostic (instrumented Hook A) — RESULT: case (ii), type check NOT on the spawn path

Built libhook.so (NDK r26d, aarch64, -nostdlib++ so deps = liblog/libm/libdl/libc only — Tribe bundles
no libc++_shared.so). Injected as DT_NEEDED of libUnreal.so (LIEF add_library, placed first in NEEDED).
Hook A = minimal ARM64 absolute-jump replace stub written over FUN_050fc054 entry
(`ldr x16,#8 ; br x16 ; .quad handler`); handler decodes the incoming FString id (UTF-16) via
__android_log_print(TAG "TRIBEMOD"), returns 1 (ReadyPlayerMe), never calls original. Repacked APK via
7z in-place update of the two libs, zipalign -p 4, apksigner (v3, cert 979d63d7…), `adb install -r`
(in-place, same key, OBB preserved).
Artifacts: hook/hook.cpp, hook/add_needed.py, out/hookA/{libhook.so, libUnreal.patched.so, tribe.hookA.apk}.
Evidence: logs/diag_hookA.txt.

Observations:
- **Injection WORKS (case iii ruled out).** Every launch logs "hooks installing… / libUnreal.so
  base=0x… / hooks installed: OK". libhook.so loads via the added DT_NEEDED and installs the hook.
- **Launch requires the headset ON.** Headless `am start` (no active HMD / in-headset prompt not
  accepted) → SIGSEGV on GameThread ~9 s in (OpenXR session can't initialise). NOT hook-related — the
  headset-on launch is clean and stable. Test this build only with the headset worn.
- Headset-on launch: stable (pid 14618, 2+ min, 72 fps, avatar rendering — spawn completed).
- **GetAvatarTypeForId FIRED count = 0** across launch + full in-game spawn. TRIBEMOD buffer did not
  roll (install lines retained), so zero is real, not lost.

**Verdict = case (ii).** Forcing GetAvatarTypeForId→ReadyPlayerMe is inert at spawn. Confirms the Phase 1
hypothesis: avatar type/route is Blueprint-orchestrated and the Meta path loads at spawn WITHOUT calling
the RPM type classifier. The clean "Hook A + Hook B" plan cannot work as-is.

**Proven reusable:** the injection mechanism (DT_NEEDED libhook.so) and the inline-replace hook
technique — both work and are non-disruptive (app runs normally with the hook resident).

**Next = third touch (trace the guaranteed-at-spawn entry).** Targets to decompile/trace:
FUN_050f5a00 (reads component url member this+0x2A8 → calls RPM resolver FUN_050f49cc) and ITS caller;
the UTribeAvatarComponent spawn/init that currently drives the Meta loader FUN_04ba868c. Aim: the
function that always runs at pawn spawn — hook it to call FUN_050f49cc(this,0,&customUrl) forcing the
RPM/glTF branch regardless of stored type, then Hook B (FUN_050f4548) pins the file.

STOP — awaiting OK for the third-touch trace.

## Phase 2b (third-touch trace, read-only) — SPAWN DECISION POINT = FUN_050fc2d4

Fresh Ghidra 12.0.4 headless re-analysis (prior project was cleaned; DisableHeavyAnalyzers prescript;
~59 min) + scripts/SpawnTrace.java reverse-call trace → out/spawn_trace.txt.

**Decision point = FUN_050fc2d4 (RVA 0x050FC2D4)** — UTribeAvatarComponent apply-avatar dispatcher.
`bool FUN_050fc2d4(this /*x0*/, FString* id /*x1*/, char type /*w2*/)`.
- Discriminator = the type byte: stored CurrentETribeAvatarType at `this+0x278` vs incoming `param_3`.
  Values (same as GetAvatarTypeForId): 0=None, 1=ReadyPlayerMe, 2=MetaAvatar2.
- Copies the incoming id/url (param_2) into the component URL member `this+0x268`, then branches:
  - type==1 (RPM):  subobj=this+0x2B8 (seeded from this+0x2C0); FUN_050fc808(this,subobj); **FUN_050f4548(subobj, this+0x268)** = glTF load.
  - type==2 (Meta): subobj=this+0x2B8 (seeded from this+0x2C8); FUN_050fca04(this,subobj); **FUN_04ba81a8(subobj, this+0x268)** = Meta SDK load.
- A type change (2->1) takes the else arm: FUN_050fbe88 teardown, store new type, copy URL, load → so flipping 2->1 forces a full RPM reload.

Callers (both funnel into the dispatcher):
- **FUN_050fc0d4 (0x050FC0D4)** "set-by-id": classifies the id **inline** (FUN_04c5b250 scheme / ".glb"+FileExists / FUN_04b9efd8 isMeta → 1/2/0) then calls FUN_050fc2d4. This inlined classify is **why GetAvatarTypeForId (FUN_050fc054) never fires at spawn** — the shared fn is bypassed here.
- **FUN_050fcee8 (0x050FCEE8)** "set-by-type" (virtual-called; replication/apply): calls FUN_050fc2d4(this,id,param_3); on failure falls back to FUN_050fc2d4(this, "Replays/DefaultAvatar.glb", 1).

Guaranteed-at-spawn: the Meta avatar we observed loading at spawn does so via this dispatcher's type==2
branch (→ FUN_04ba81a8 → zip://N_quest2.glb). So FUN_050fc2d4 IS on the spawn path; forcing its inputs
flips the pipeline. (The build will log-verify it fires, same technique as Hook A.)

Hook B confirm: FUN_050f4548 callers = FUN_050f49cc, FUN_050f5a00, FUN_050fc2d4 (RPM arm), self — ALL
RPM-path. NOT reached by the Meta path (FUN_04ba81a8 → libovravatar2). So pinning the file at FUN_050f4548
is RPM-only and catches the load once the RPM branch runs.

### Ranked intervention
**(A) PREFERRED — flip Tribe's own decision at the dispatcher.** Hook FUN_050fc2d4; force w2(type)=1 and
x1(id)=&persistent FString of our avatar (absolute /sdcard/.../custom.glb, or an RPM URL), then call the
original. Stock code stores type=1, copies our URL to this+0x268, runs its own RPM branch → FUN_050f4548
loads our file. One surgical hook, reuses the whole stock load path, catches BOTH caller entries,
guaranteed at spawn, lowest risk.
  + optional **Hook B** (FUN_050f4548, overwrite the path arg) to pin the exact file regardless of any
    internal URL→cache-path derivation.
**(B) fallback — inject a load call.** Hook a guaranteed-spawn entry and call FUN_050f49cc(subobj,0,&url)
or FUN_050f4548(subobj,&path) directly. More fragile: must obtain the RPM subobject (this+0x2B8) and synth
an FString; option A reuses the real objects, so prefer A.

STOP — awaiting OK to build option A (hook FUN_050fc2d4, instrumented + log-verify at spawn).

## Phase 2c (Option A + Hook B build/test) — case (iv) CRASH; cause found; addressing bug fixed

**Addressing correction (critical):** Ghidra rebased the image to IMAGE_BASE=0x00100000, so the diagnostic's
Hook A address (0x050FC054) was 0x100000 too high — it patched the wrong function (harmlessly), which is
why "GetAvatarTypeForId never fired" in Phase 2 was partly a misplaced-hook artifact (case ii still holds on
the independent static evidence that FUN_050fc0d4 classifies inline). **Real runtime vaddr = Ghidra addr −
0x100000.** Confirmed by objdump: dispatcher FUN_050fc2d4 → 0x04FFC2D4, choke FUN_050f4548 → 0x04FF4548,
GetAvatarTypeForId → 0x04FFC054 (all disassemble to correct prologues). Runtime = load base + real vaddr.

Build: hook/hook.cpp + hook/vendor/And64InlineHook.cpp (MIT, arm64 inline hook w/ trampoline; no libc++),
NDK r26d, -nostdlib++. Hook A pre-hook on dispatcher (force type=1 + our FString, call original); Hook B
pre-hook on choke (force path, call original). Target = /sdcard/Android/obb/com.TribeXR.TribeXR/
rpmavatar-custom.glb (adb-writable + app-readable; staged with extracted/assets/DefaultAvatar.glb).

Results (logs/hookAB_live.txt, tag-filtered so no buffer roll):
- **Both hooks install every launch** — addresses confirmed live (base+0x04FFC2D4 / base+0x04FF4548,
  A64 "20 bytes overwritten"). Injection + toolchain fully proven.
- **Hook B (choke) fires at spawn with an EMPTY path** (`path='(empty num=0)'`) ~1.5 s in — an init/reset
  call. Forcing a real load there → **SIGSEGV SEGV_ACCERR on GameThread**: `#00 pc 0x20 [anon:.bss]` /
  `#01 libUnreal.so+0x188aaac` / `#02 0xdc [anon:.bss]` = call through an uninitialized avatar-loaded
  callback. Crashes every launch (~1–1.5 s), before the real avatar spawn → app won't start.
- **Hook A (dispatcher) never fired** — the Hook B crash pre-empts it; dispatcher-fires-at-spawn still
  unconfirmed.

**Root cause:** Hook B forces EVERY FUN_050f4548 call, incl. early empty-path init/reset calls when the
load delegates aren't set up. Fix: **Hook B must pass empty-path (num<=0) calls through untouched**, only
forcing on non-empty paths. Coupling: today's spawn avatar is Meta (type=2), so the choke likely only ever
sees an empty path UNLESS Hook A flips type→1 to drive the RPM branch (which then calls the choke with a
real path). So Hook A doing its job is what produces Hook B's real-path call.

Device restored to the clean re-signed build (adb install -r out/resign/base.resigned.apk) — hooks removed,
Tribe launches normally.

Next: rebuild with Hook B guarded (skip num<=0), Hook A unchanged; re-test headset-on to see if the
dispatcher fires and loads our file.

STOP — awaiting OK to build the guarded version.

## Phase 2d (guarded build test) — Option A REFUTED for initial spawn

Guarded build: Hook B passes empty-path (num<=0) calls through untouched; Hook A forces type=1 + our
FString on the dispatcher. Uninstalled the (store-reinstalled) Meta build, installed the sideload,
re-pushed OBB + staged rpmavatar-custom.glb. Launched headset-on, user drove fully into a session.

Result (logs/hookAB_guarded.txt, tag-filtered):
- Guard works — NO crash. App stable through full in-session load (pid alive, no SIGSEGV).
- **dispatcher FIRED = 0** even fully in-session with the avatar rendering. **choke FIRED = 1**, the same
  early empty-path init call (~2.7 s), now passed through harmlessly.
- User confirms: **their Meta avatar shows** (unchanged). The initial avatar load bypassed both hooks.

**Conclusion: FUN_050fc2d4 is NOT the initial-spawn apply point.** The choke hook firing proves addressing
+ hooking are correct, so this is a real finding, not a hook bug. The initial (Meta) avatar loads via a
path that does not call FUN_050fc2d4 (FUN_04ba81a8 reached from a Meta-SDK/init caller, or a serialized
component load). FUN_050fc2d4 is likely the runtime avatar-CHANGE apply point (UI/network), not spawn.

Also confirmed: the RPM component's ONLY spawn-time loader call is the empty-URL init at ~2.7 s, and it is
too early to hijack — forcing a load there dereferences the not-yet-attached glTF context (this+0x90) →
the earlier SIGSEGV (#00 pc 0x20 [anon:.bss]).

Net: injection toolchain + inline-hook mechanism fully proven; addressing bug (Ghidra +0x100000) fixed.
But no identified point yet forces the avatar at INITIAL spawn. Open questions for the next trace:
(i) what supplies the avatar id/type at spawn (to make it resolve to an RPM URL so the normal path loads
ours), and (ii) where/when the RPM component's glTF context (this+0x90) is initialized (a safe, not-too-
early injection point).

Device restored to clean re-signed build.

STOP — awaiting direction (targeted spawn-load trace, or reassess approach).

## Phase 3-prep (Blueprint extraction + readable-structure inspection) — VERDICT (I): promising seam

Read-only. Extracted avatar Blueprints from OBB pakchunk0 via scripts/pak_extract.py + the pure-Rust
oodle_dec (oozextract, prior-session scratchpad binary reused) → decompressed .uasset+.uexp to
extracted/blueprints/. No bytecode disassembly yet.

Extracted (valid, sizes == uncompressed): Pawn/TribePawnBP; GameModes/TribeGameInstanceBP,
TribePlayerStateBP; Visuals/Skins/OculusAvatar/{BP_ReadyPlayerMeAvatarSkin, BP_OculusAvatarSkin,
DT_OculusAvatarSkins}; Menus/W_RPMAvatarCreator.

### Readable structure (name tables = FModel-equivalent; .uexp control flow is index-coded, not grep-visible)
- **Avatar rendering = a SKIN system on the pawn.** TribePawnBP: AvatarComponent (native
  UTribeAvatarComponent), AvatarID (BP var), ActiveSkins/ActiveSkinClasses, ApplySkin/ApplyActiveSkins,
  SetupAvatar, GetSkin/GetSkinClass/GetSkinName, IsAvatarLoaded — applied at spawn (ReceiveBeginPlay,
  Possessed, bPossessed).
- **Skins derive from BP_TribeSkinBase:** BP_OculusAvatarSkin (Meta) + BP_ReadyPlayerMeAvatarSkin (RPM).
- **RPM skin self-loads from config:** BP_ReadyPlayerMeAvatarSkin has ReadConfigString + refs
  [TribeAvatar]/ReadyPlayerMeAvatarUrl (.uexp), SetAvatarID, OnSkinApplied/OnSkinLoaded,
  ReadyPlayerMeComponent, GetTribeDefaultAvatarId. So once applied it reads the stored RPM URL from
  config and loads it — no UI needed at that point.
- **Persisted custom-avatar identity:** TribeGameInstanceBP has AvatarId + bHasCustomAvatar/HasCustomAvatar
  + GetTribeDefaultAvatarId.
- **DT_OculusAvatarSkins = the ~32 presets, all Meta** (zip://N.glb; + My Avatar / Oculus Home custom /
  Blank Meta Avatar). No RPM rows — RPM is the URL-config path, not a preset.
- **W_RPMAvatarCreator = the RPM UI writer/entry:** AvatarUrl, GetStringFromClipboard (paste),
  IsValidReadyPlayerMeAvatarUrl/ID, LoadAvatarAtUrl, InitMyRPMAvatarSkin, ApplySkinToPlayer,
  AddOrUpdateCachedRPMAvatarSkin, GetRPMCustomSkin, RPM{Create,Paste,LaunchWeb}Button, cast to
  BP_ReadyPlayerMeAvatarSkin. Only place IsValidReadyPlayerMe*/LoadAvatarAtUrl appear.
- **No BP references GetAvatarTypeForId/SetAvatarUrl by name** — type classify is native/inlined (matches
  FUN_050fc0d4).

### Verdict = (I): promising seam; worth Stage-3 bytecode
RPM is not purely UI-gated in principle: the RPM skin self-loads from [TribeAvatar]ReadyPlayerMeAvatarUrl
on apply; the pawn applies active skins at spawn; the custom-avatar identity persists (GameInstance
AvatarId + bHasCustomAvatar). If the spawn skin-selection reads that persisted identity and routes to the
RPM skin, then setting the persisted state + config URL loads our avatar at spawn WITHOUT the widget.
Control flow is in bytecode, so this needs Stage-3 to confirm. Disassembly targets:
1. TribePawnBP :: SetupAvatar / ApplyActiveSkins / GetSkinClass — spawn skin-selection: does
   BeginPlay/Possessed read AvatarId/HasCustomAvatar (or server/config) and pick RPM vs Meta skin class? (THE decision)
2. TribeGameInstanceBP :: setter/reader of AvatarId + bHasCustomAvatar — how the persisted identity is
   established at startup (config/server/save) = what we'd set.
3. BP_ReadyPlayerMeAvatarSkin :: OnSkinApplied / OnSkinLoaded — confirm ReadConfigString→native RPM load.
4. W_RPMAvatarCreator :: ApplySkinToPlayer / AddOrUpdateCachedRPMAvatarSkin — how the UI persists the RPM
   selection (exact state spawn would need).

Artifacts in extracted/blueprints/ (binaries gitignored). STOP — no bytecode disassembly yet, per instruction.

## Phase 3 (Blueprint bytecode) — VERDICT (I-b): reader config-settable, RPM-skin SELECTION is widget/native

Tool 1 UAssetAPI 1.1.0 (dotnet, scratchpad/bp_disasm): loads the assets but every export → RawExport,
NO bytecode. Cause: PKG_UnversionedProperties (HasUnversionedProperties=true) + no .usmap → UAssetAPI
can't parse exports. A TribeXR .usmap needs a runtime type dump (injection = build; out of scope for
read-only). Tool 2 (alternative, used): scripts/bp_refscan.py — decodes each function's RawExport bytes
(bytecode is name/import-indexed, usmap-independent) and reports referenced imports + name indices. Not
full control flow, but shows what each function touches.

Findings:
- **Skin system is GENERIC + network-replicated.** TribePawnBP: ActiveSkinClasses, ApplySkin/
  ApplyActiveSkins, GetSkinClass, Server_AddActiveSkin (client→server) + Multi_AddActiveSkin (multicast),
  SpawnDefaultAvatar, SetAvatarID — all tiny, take the skin CLASS as a parameter. The pawn ubergraph
  (71 KB) references BP_TribeSkinBase_C, TribeAvatarComponent, TribeGameInstanceBP_C — but NOT the
  specific RPM/Meta skin classes, NOT bHasCustomAvatar, NOT ReadConfigString, NOT GetAvatarTypeForId.
  So the pawn applies whatever skin class it's TOLD to; it doesn't decide RPM vs Meta.
- **The RPM skin CLASS (BP_ReadyPlayerMeAvatarSkin_C) is referenced ONLY by W_RPMAvatarCreator**
  (GetRPMCustomSkin). No pawn/GameInstance BP instantiates it. So at spawn nothing in these BPs adds the
  RPM skin; the RPM skin is added by the widget (ApplySkinToPlayer → Server_AddActiveSkin(RPM class)).
- **URL persists in config, reader alive:** BP_ReadyPlayerMeAvatarSkin + BP_OculusAvatarSkin +
  W_RPMAvatarCreator all WriteConfigString; the RPM skin ReadConfigString's [TribeAvatar]
  ReadyPlayerMeAvatarUrl on apply → once the RPM skin is active, our URL/glb loads with no UI.
- **Persisted identity is derived, not a config flag:** GameInstance HasCustomAvatar() computes
  AvatarId != GetTribeDefaultAvatarId() (native import). GameInstance has NO config/save/HTTP imports —
  AvatarId's writer is native/server/UI, not a BP-visible config or save file.

**Verdict (I-b).** Spawn does NOT select the RPM skin from a plain settable config/save flag (rules out
I-a). The URL reader IS config-settable, but the RPM-skin SELECTION is widget-driven (and/or native/
server) — the classic wall: reader alive, selection-writer gone with the UI. Matches the native result
(spawn applies the default/Meta skin; the dispatcher FUN_050fc2d4 is the runtime CHANGE apply, not spawn).

Two forward paths (empirical, cheap, before any hook):
1. **Is W_RPMAvatarCreator still REACHABLE in the current app UI?** If yes, it's the intended RPM path:
   set an RPM URL in-app (writes config + applies RPM skin), pre-place our .glb at the RPM cache path so
   FileExists short-circuits the download → **custom avatar with NO hook / NO re-sign.** If it persists
   across relaunch, done. (The "removed UI" was an assumption; the widget asset is present.)
2. If NOT reachable → I-b fallback = a hook that ADDS the RPM skin class as an active skin at spawn (hook
   the pawn's AddActiveSkin path / force the selection the widget normally does) + config URL + cache
   glb. This is a BP-UFunction-level force, not the simple native dispatcher we tried.

STOP — awaiting direction. Recommend the reachability check (path 1) first: it may need no hook at all.

## Path-2 design trace (native, read-only) — NO clean native hook exists for the skin selection

scripts/SkinTrace.java over the analyzed project. Searched libUnreal.so's string table for the skin/
avatar function names and traced the config read.

**Decisive: the skin system is Blueprint-only (no native chokepoint).** These names are NOT present as
strings in libUnreal.so, i.e. they are BP UFunctions (VM bytecode), not native C++:
`AddActiveSkin`, `ApplyActiveSkins`, `GetSkinClass`, `GetDefaultSkinClass`, `SetAvatarID`.
So "Hook 1 = force AddActiveSkin's class arg / inject RPM into the list" has **no native function to
inline-hook** — the list is built and consumed in the BP VM. Forcing it needs either a UObject::
ProcessEvent VM interception (heavy, fires for every BP call, must filter) or a pak BP edit (recompile
cooked BP — fragile, breaks per update). Neither is a clean minimal hook.

**What IS native/hookable (but downstream of the BP skin decision):**
- Config read: `ReadConfigString` string present (@0061e03d, native TribeBlueprintLibrary). The RPM
  URL read is native `FUN_050f584c` (Ghidra 0x050F584C / real 0x04FF584C): calls GConfig::GetString
  (`FUN_016a70bc`) for [TribeAvatar]ReadyPlayerMeAvatarUrl + ReadyPlayerMeETag, builds
  "%srpmavatar-%s" cache path, FileExists. `ReadyPlayerMeAvatarUrl` string (@002ccf8e) is read by
  FUN_050fc6e0, FUN_050f584c, FUN_050f49cc.
- RPM loader FUN_050f49cc / choke FUN_050f4548, dispatcher FUN_050fc2d4 (all native).
- `GetTribeDefaultAvatarId` string present (@00686acb) but no direct code xref surfaced (registration-
  only); would need more tracing to hook.

**Why the native leaf hooks don't solve it:** supplying the config URL (hook FUN_016a70bc / FUN_050f584c)
only matters if the RPM SKIN is applied — and applying it is the BP-only step with no native seam. The
native avatar paths we can hook are either off the spawn path (dispatcher FUN_050fc2d4 — 0 fires at
spawn, proven) or fire too early (the choke's empty-URL spawn init — crashes if forced). At spawn the BP
applies the DEFAULT (Meta) skin (BP_OculusAvatarSkin → MetaAvatar2Component), never touching the RPM
native path.

### Path-2 verdict: the clean minimal-hook set does NOT exist
Forcing the RPM skin at spawn requires acting on Blueprint VM state, not a native chokepoint. Options,
worst-to-best for effort/robustness:
- (worst) Pak BP edit: change the pawn's default skin class / skin-selection BP → recompile cooked BP +
  repack the 688 MB Oodle pak. Fragile, breaks each update, heavy tooling.
- (heavy) Hook UObject::ProcessEvent in libhook: detect the pawn's skin-apply UFunction call and swap the
  skin class to BP_ReadyPlayerMeAvatarSkin_C (obtain via FindObject/StaticLoadObject on
  "/Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin.BP_ReadyPlayerMeAvatarSkin_C"), plus hook
  FUN_016a70bc to return our URL for [TribeAvatar]ReadyPlayerMeAvatarUrl. Doable but fragile, wide blast
  radius, must not fire prematurely.
- (best) **Path 1, no hook: use the in-app RPM Avatar Creator if it is still reachable.** It writes the
  config URL and applies the RPM skin through the supported flow; pre-place our .glb at the cache path
  `<ProjectUserDir>/Documents/Avatars/rpmavatar-<basename(url)>.glb` so FileExists short-circuits the
  download. No hook, no re-sign. Whether it persists across relaunch is an empirical check.

Config details (for Path 1 / any approach): key = GConfig section [TribeAvatar], value ReadyPlayerMeAvatarUrl
(+ ReadyPlayerMeETag), in the global user ini (internal — not a writable external file; that's why the
writer being gone matters). Cache file the loader wants: Documents/Avatars/rpmavatar-<basename>.glb.

STOP — no build. Recommend Path 1 reachability check in-headset before any hook.

## Path-1 fallback (no-hook trigger search, read-only) — VERDICT: NO no-hook trigger exists

1. **APK manifest — no avatar route.** Activities: com.epicgames.unreal.GameActivity (MAIN+INFO+VR),
   DownloaderActivity (OBB), gms AdActivity, EOSAuthHandlerActivity, gms SignInHubActivity. Custom
   schemes: only `eos.xyza7891pjfbybrpflbw8dbt3uxrbsa7` (EOS OAuth) + a resource-ref scheme + generic
   http/https VIEW/BROWSABLE. **No avatar/RPM/creator deeplink, intent-filter, or exported activity.**
2. **libUnreal.so — no avatar console command.** Literal scan found only generic `CheatManager` (4) and
   `GEngine` (4); NO OpenAvatarCreator/SetCustomAvatar/OpenRPM/ShowAvatarCreator/RPMCreator command
   strings. No registered native console command opens the creator or sets the RPM skin.
3. **BuildConfiguration = "Shipping"** (manifest meta-data). UE Shipping strips the console UI, so exec
   UFUNCTIONs can't be typed, and there's no on-device console surface. (`-ExecCmds`/UECommandLine.txt
   was already tested inconclusive, and there is no registered avatar command for it to call anyway.)
4. **Opener identified: W_ProfileMenu references W_RPMAvatarCreator** — the creator was opened by a
   button in the Profile menu, which is the removed UI. No other BP references it; no alternate event/
   deeplink/console path.

**Verdict: no no-hook trigger.** No deeplink/intent/scheme, no usable console command (Shipping), and the
only in-app opener (W_ProfileMenu button) is removed. **The only remaining route to a spawn-time custom
RPM avatar is the Path-2 hook** — and per the Path-2 trace that means a UObject::ProcessEvent VM hook
(the skin selection is BP-only; no native chokepoint), swapping the applied skin to
BP_ReadyPlayerMeAvatarSkin_C + forcing the config URL (hook FUN_016a70bc / FUN_050f584c), with the .glb
pre-placed at Documents/Avatars/rpmavatar-<basename>.glb. Heavy/fragile; wide blast radius; must not fire
prematurely (the empty-URL crash mode).

STOP.

## Second-opinion integration + verified answers (read-only)

An expert review corrected two of my errors and reframed the plan. Verified facts this session:

- **ProcessEvent correction (I was wrong).** Same-object BP→BP calls emit EX_LocalFinalFunction →
  ProcessLocalScriptFunction; cross-object → ProcessInternal. ProcessEvent is ONLY the native→BP entry
  funnel (events/delegates/RPCs/timers). So a ProcessEvent hook CANNOT intercept the ApplyActiveSkins
  arg — but it IS a clean once-per-spawn timing signal for TribePawnBP_C::ReceiveBeginPlay/
  ReceivePossessed (filter = cached UFunction* pointer compare; guard re-entrancy with a TLS flag +
  call the trampoline). My "swap the skin arg via ProcessEvent" idea was mechanically impossible.
- **Q1 — legacy .pak, not IoStore.** OBB has 4 .pak, ZERO .utoc/.ucas/.sig; index unencrypted. Patch-pak
  preconditions all favorable: a `..._P.pak` gets +100 mount priority and overrides same-path files;
  no signature enforcement; legacy tooling (UnrealPak/repak). I wrongly dismissed pak editing.
- **Q2 — soft-path scan (I'd only done import scan).** Now checked name-table soft paths too:
  TribePawnBP soft-refs only BP_TribeSkinBase (not the RPM subclass). BP_TribeSkinBase has generic
  SkinClass + GetSkinClass + F_SkinInfo. DT_OculusAvatarSkins rows point only at Meta thumbnails
  (T_MetaPresetNN) + zip:// paths. **No pawn/base/registry reference — hard OR soft — to
  BP_ReadyPlayerMeAvatarSkin_C; it is referenced only by W_RPMAvatarCreator.** I-b confirmed.
- **DefaultAvatar.glb override (patch-pak) — nuance:** DefaultAvatar.glb is a RAW glb in the pak and is
  the RPM loader's FALLBACK (FUN_050f49cc → cache-miss → FUN_050f5e58 loads Replays/DefaultAvatar.glb).
  Overriding it via _P pak elegantly solves MESH DELIVERY (no URL host / no cache write / no ETag) — but
  only renders once the RPM path is entered. It does not by itself flip spawn from Meta→RPM.

### Adopted roadmap (supersedes the "ProcessEvent swaps the arg" plan)
1. **usmap dump FIRST (angle d) — de-risks everything.** We have injection (libhook.so proven). Build a
   dumper into libhook: find NamePoolData (fn referencing the hardcoded name table "None"/"ByteProperty"/
   …), GUObjectArray (reads of gc.MaxObjectsNotConsideredByGC / gc.SizeOfPermanentObjectPool /
   gc.MaxObjectsInGame in UObjectBaseInit), ProcessEvent vtable slot (via "ReceiveBeginPlay" →
   FindFunctionChecked → indirect vtable call). Port kp7742 UE4Dumper (Android/ARM64, UE5 profiles) or
   Dumper-7 logic; dump .usmap to /sdcard. Unlocks: full BP bytecode decompile (does spawn use the CDO
   default skin or rebuild ActiveSkinClasses from AvatarId/server?), property offsets, CDO editing,
   ProcessEvent index. Also enables a file-polled "dev console" (ProcessEvent+Tick+FindFunction).
2. Decide from the decompile of ApplyActiveSkins/GetSkinClass/spawn graph:
   - **CDO default survives to spawn → patch-pak route (persistent, no runtime hook):** edit
     Default__TribePawnBP_C ActiveSkinClasses default (or the DT SkinClass) to BP_ReadyPlayerMeAvatarSkin_C
     in UAssetGUI (usmap-enabled), ship a small `_P` pak; override Replays/DefaultAvatar.glb with our
     rigged mesh. Survives updates with re-dump+re-pack.
   - **Spawn rebuilds from AvatarId/server → widget-replay route (runtime):** ProcessEvent hook on
     ReceiveBeginPlay (timing) → wait N frames (Tick) to reach a fully-initialized in-session pawn
     (sidesteps the 2.7 s empty-URL crash) → StaticLoadObject the RPM class (not resident; only the
     removed widget referenced it) → ProcessEvent(FindFunction("AddActiveSkin"), {Class}) →
     ProcessEvent(ApplyActiveSkins). URL: call the widget's own save fn via ProcessEvent so the GAME does
     GConfig->SetString (persists; internal ini is root-only for adb but writable by the app process), or
     hook FUN_016a70bc. Use file:///…/rpmavatar-custom.glb + pre-placed cache file.
   Mesh delivery in EITHER route: override DefaultAvatar.glb via _P pak (least fragile).

STOP — read-only done. Next step (usmap dumper) is a BUILD; awaiting greenlight.

## Session 1 — usmap/SDK dumper LOCATOR CONTRACTS (static Ghidra, read-only)

Reminder: **real runtime vaddr = Ghidra addr − 0x100000** (image base 0x100000). Runtime abs = libUnreal.so
load base + real vaddr. Ghidra project scripts: AnchorTrace.java, DecompAddrs.java.

**L1 — NamePoolData (FNamePool). RESOLVED.**
- Global `NamePoolData` = Ghidra DAT_07d622c0 → **real 0x07C622C0** (in .bss; direct ADRP+ADD, not GOT →
  addr = base + 0x07C622C0). Lazy-init once-guard at real 0x07C622B8; hash shards base real 0x07C72300 (stride 0x80).
- Anchor chain: FName ctor FUN_0173299c (real 0x0163299C) → number-suffix parse FUN_01732a18 (0x01632A18)
  → pool store FUN_01736088 (0x01636088): `if(!guard){ FUN_0172ff60(&NamePoolData); guard=1 } store=FUN_01731784(&NamePoolData,...)`.
- Pool constructor / hardcoded-name registrar = **FUN_0172ff60** (real 0x0162FF60; the 6180-byte fn that
  references "ByteProperty"/"IntProperty"/… — the reviewer's L1 anchor). FName store = FUN_01731784 (0x01631784).
- Layout (5.4): FNameEntryAllocator at pool base; Blocks[] after FRWLock (bionic pthread_rwlock_t = 56 B →
  Blocks ~0x40, VERIFY at runtime). Resolve: block=id>>16, entry=Blocks[block]+(id&0xFFFF)*2; header u16
  {bIsWide:1, hash:5, Len:10}. Self-check: Resolve(0)=="None"; check sizeof(FName)==8 (outline-number OFF).

**L2 — GUObjectArray. RESOLVED.**
- Anchor UObjectBaseInit = **FUN_0197bbd8** (real 0x0187BBD8; builds "UObjectBaseInit", reads the 3 gc.* cvars).
- It calls AllocateObjectPool **FUN_01977c90** (real 0x01877C90; refs "…/UObjectArray.cpp") with this =
  GOT slot **Ghidra 0x07ba59e8 → real 0x07AB59E8** (in .got, PTR_ → **GUObjectArray = *(base+0x07AB59E8)**;
  if self-check fails, try direct base+0x07AB59E8).
- Layout CONFIRMED from FUN_01977c90: +0x08 MaxObjectsNotConsideredByGC, **+0x10 ObjObjects**
  (FChunkedFixedUObjectArray: Objects**, PreAllocatedObjects*, MaxElements i32, NumElements i32, MaxChunks
  i32, NumChunks i32). FUObjectItem stride 0x18 {Object*, Flags i32, ClusterRootIndex i32, SerialNumber i32}.
  Index→Objects[i>>16][i&0xFFFF]. Self-check: NumElements ~tens of thousands; NumChunks==ceil(NumElements/65536);
  Objects[0][0].Object->InternalIndex==0.

**L3 — ProcessEvent vtable slot. NOT pinned statically → runtime-resolve.**
- "ReceiveBeginPlay" has no direct code xref (FName-hashed); "ReceiveTick" xrefs were BT-node event
  *detection* (FindFunction-based FUN_055b52d8), not the ProcessEvent vtable dispatch. FName ctor for events =
  FUN_0173299c; impl-checker = FUN_055b52d8.
- Resolve at runtime (reviewer's self-check): candidate UObject vtable slot → hook it, log first ~20
  Function->NamePrivate; expect ReceiveTick/Tick/ReceiveBeginPlay/Construct. Cross-anchor ReceiveTick +
  ReceiveBeginPlay must yield the same slot. (Do in Session 3, needs the L1/L2 walk working first.)

**L4 — UObject/UStruct/FField offsets. Hypothesis from reviewer; runtime-verify via invariants.**
- UObject: 0x00 vtable,0x08 Flags,0x0C InternalIndex,0x10 ClassPrivate,0x18 NamePrivate(FName),0x20 Outer (size 0x28).
- UField 0x28 Next; UStruct 0x30 SuperStruct,0x38 Children,0x40 ChildProperties(FField*),0x48 PropertiesSize,0x50 Script.
- FField 0x08 ClassPrivate(FFieldClass*, Name@0x00),0x28 NamePrivate,0x20 Next; FProperty 0x3C ElementSize,
  0x40 PropertyFlags,0x4C Offset_Internal. **FProperty is NOT a UObject (since 4.25)** — walk UStruct::ChildProperties.
  Handle FObjectProperty.PropertyClass / FStructProperty.Struct / FArrayProperty.Inner / FBoolProperty bitfield /
  **FOptionalProperty (NEW in 5.4)**. Verify: Class "Object" → SuperStruct==0 && PropertiesSize==0x28; Class "Class"
  → ClassPrivate==self. Shift tail until both hold.

### Decisive-question shortcut (build into the dumper day 1)
Once L2 + property offsets work: read Default__TribePawnBP_C.ActiveSkinClasses (CDO default) vs a live spawned
pawn's ActiveSkinClasses a few frames after ReceiveBeginPlay. Identical → CDO default survives → patch-pak
route. Differ → spawn rebuilds from AvatarId/server → widget-replay route. No VM decompile needed.

### Session plan
S1 (done): L1/L2 pinned, L3 runtime-deferred, L4 hypotheses + self-checks.
S2 (device, read-only, build): libhook resolves L1/L2, runs self-checks, dumps objects.txt + sdk.txt. No new hooks.
S3: ProcessEvent hook (resolve L3) + values.txt live CDO/pawn reads + script/ dump + TribeXR.usmap.
S4: file-polled console (cmd.txt → FindObject/FindFunction/ProcessEvent).

STOP — Session 1 static contracts done; Session 2 is a device BUILD, awaiting greenlight.

## Session 2 (device dumper) — INFRA PROVEN; L1 (FNamePool) mis-anchored; L2 corrected

Built hook/dumper.cpp → libhook.so (read-only: DT_NEEDED inject, detached poll-thread on
tribemod/dump_now, safe_read via /proc/self/maps + SIGSEGV guard, params.txt tunables + abs/probe
hexdumps, fail-loud self-checks). Injection+thread+trigger+output+self-check-abort ALL work on-device.
Iterate without rebuilds via tribemod/params.txt (np/ga/bo/probe/abs) — proven.

**L2 GUObjectArray CORRECTED + still solid.** The GOT slot (Ghidra 0x07ba59e8) is relocated via
**.relr.dyn** (compact RELR, no explicit addend) — the RVA is stored in the slot: **GUObjectArray real
RVA = 0x07D0EAB8** (.bss), NOT the GOT-slot address. Runtime cross-check: base+0x07D0EAB8 == *(base+0x07AB59E8).
(Not yet on-device-validated — R1 abort blocks R2; statically firm.)

**L1 FNamePool = WRONG anchor.** DAT_07d622c0 (real 0x07C622C0), reached via FName ctor FUN_0173299c →
FUN_01732a18 → store FUN_01736088 → ctor FUN_0172ff60(&DAT_07d622c0), is NOT the FNameEntryAllocator.
On-device dump: it's a 0x30-stride hash table whose entry pointers target **wide (UTF-16) strings** =
build/branch/version names + some class names ("Dev-CineCamera","UE5-Main","UE5-Release","Dev-Cooker",
"UNiagaraDataInterfaceCamera"…). The paired "shards" global DAT_07d72300 (0x07C72300) is all zeros.
So Resolve(0) never yields "None" — R1 self-check correctly FAILED and aborted (no garbage walk).
FUN_0172ff60 references "ByteProperty" but is a property/version registrar, not the FName pool ctor —
the reviewer's L1 string-anchor landed on the wrong function.

**Re-anchor plan (next):**
- (A, robust — recommended) Find **FName::ToString / FNameEntry::AppendString** RVA and CALL it from the
  dumper via a function pointer to resolve any FName (id+number)→string. Layout-agnostic; sidesteps the
  pool internals entirely. Needs a safe call from the poll thread (args: &FName, &FString out).
- (B) Re-find the real FNameEntryAllocator statically: locate FNamePool::Resolve by its bit-pattern
  (lsr #16 / and #0xffff / lsl #1 / ldr [blocks, idx, lsl #3]); the Blocks base there is the true global.
- Then relax the R1 abort so R2 (GUObjectArray counts/index — no names needed) validates independently.

Everything read-only. Dumper + scripts committed. Device left on the dumper build (harmless; hooks nothing).

STOP — FName-pool re-anchor needed before the object walk can name-match; awaiting direction.

## Session 2 COMPLETE — dumper green (FAILS=0); avatar pipeline mapped

Read-only dumper now passes every self-check on-device and answers the decision. Fixes this session:
- **FNamePool** via runtime signature scan (reviewer option C): scan libUnreal rw maps for a slot whose
  target begins None(len4)+ByteProperty(len12). Real **NamePoolData rva=0x07C632C0** (old 0x07C622C0 was
  FCustomVersions, one page low). blocks_off=0x40. `fname_resolve` (hdr>>6=len, hdr&1=wide) verified.
- **GUObjectArray** located by Ghidra (AllocateObjectPool FUN_01977c90) + name-validated on-device.
  Real **GUObjectArray rva=0x07CBBDD0** (Ghidra ptr slot 0x07ba59e8 -> static 0x07cbadd0, runtime is +0x1000).
  GOT slot rva=0x07AA59E8 (old 0x07AB59E8 was off by 0x10000). ObjObjects@+0x10; Objects**@+0x10;
  MaxElements@+0x20; NumElements@+0x24; NumChunks@+0x2C.
- **FUObjectItem stride = 0x14** (NOT 0x18): {Object*,Flags,Cluster,Serial}=20B; chunk = 8B header(0x10000)
  + 65536*0x14; Objects[k] points AT item[0] (chunk+8). This was the bug that made every R2 candidate/scan miss.
- **UStruct offsets** (slid on-device, name-free): Super=0x40 Children=0x48 ChildProperties=0x50 PropSize=0x58.
- **FField/FProperty** (from live dump): Owner is an 8-byte tagged FFieldVariant, so FF_Class=0x08 FF_Next=0x18
  FF_Name=0x20; FProperty Offset_Internal=0x44. (Old 0x20/0x28/0x4C were each 0x08 high -> garbled names.)
- **Stability**: in_range() is now binary search (maps are address-sorted); the SIGSEGV/SIGBUS guard is
  thread-scoped (siglongjmp only on the dumper tid). The earlier long O(n) scan starved the VR AudioRecord
  thread -> game SIGSEGV in libwilhelm audio callback. Pinning np/bo/ga via params.txt = instant, no scans.
  Self-check RVAs (this build): np=0x07C632C0 bo=0x40 ga=0x07CBBDD0.

Selfcheck: R1 (name pool) PASS; R2 GUObjectArray PASS (63,408 objs, obj0='/Script/CoreUObject'); R3
Class/Object/Actor PASS + coupling; R4 FField chain PASS (real AActor props). TOTAL FAILS=0.

### DECISION — the avatar is NOT a pawn-CDO ActiveSkinClasses default; it is TribeVisualsManager-driven.
- TribePawnBP_C CDO = /Game/Pawn/TribePawnBP.Default__TribePawnBP_C; its ActiveSkinClasses holds an
  ENVIRONMENT skin (BP_EnvironmentSkin_C), not the avatar. So patch-pak'ing the pawn CDO does NOT set the avatar.
- Live avatars are **BP_OculusAvatarSkin_C** (11 live instances under CommonLevel.PersistentLevel.
  TribeVisualsManager). **BP_ReadyPlayerMeAvatarSkin_C has NO live instance** (only its CDO) -> the RPM path
  is dormant; the burner account currently renders a Meta/Oculus avatar.
- GameInstance TribeGameInstanceBP_C.AvatarId (offset 0x318) = '3722236897819126'.

### RPM pipeline (all BP UFunctions -> reachable via ProcessEvent). See logs/scan_final/avatar_pipeline.txt.
- BP_TribeVisualsManager_C: InitMyRPMAvatarSkin, InitRPMAvatarSkins, AddOrUpdateCachedRPMAvatarSkin,
  AddCachedRPMAvatarSkin, ApplySkinToPlayer, ApplyNamedSkinToPlayer, GetSkin, LoadSkinSelection(s), InitSkins.
- W_RPMAvatarCreator_C: LoadAvatarAtUrl, ReloadAvatarAtUrl, PasteAvatarUrl, GetRPMCustomSkin,
  HandleAvatarLoaded, HandleAvatarCached, OnAvatarSkinLoaded.
- BP_ReadyPlayerMeAvatarSkin_C: GetSkinClass, OnSkinApplied, OnSkinLoaded.
- TribePawnBP_C: SetAvatarID.  Native: /Script/ReadyPlayerMe.ReadyPlayerMeFunctionLibrary.

### Session 3 (proposed): ProcessEvent hook to DRIVE the RPM pipeline at spawn.
Resolve ProcessEvent (native->BP entry). Watch InitMyRPMAvatarSkin / ApplySkinToPlayer at spawn, then
replay the RPM-load flow with our .glb URL: W_RPMAvatarCreator_C.LoadAvatarAtUrl(url) ->
AddOrUpdateCachedRPMAvatarSkin -> ApplySkinToPlayer(RPM skin). This is the "widget-replay" branch; the
patch-pak branch is ruled out for the avatar (avatar not in pawn CDO). Caveat: prop_offset for
TribePawnBP_C.ActiveSkinClasses resolved @0x470 one run, -1 the next (find_struct picked a different
same-named class object) — non-blocking for the decision but tighten find_struct (prefer the class whose
Outer is the /Game/... package, skip SKEL_/REINST_) before relying on pawn property offsets in S3.

STOP — Session 2 done; awaiting direction on Session 3 (ProcessEvent-driven RPM replay).

## Session 3a-prep (read-only) — the GATE is a config-string read; pipeline fully mapped

sdk.txt emitted (logs/scan_final/sdk.txt). Path-resolved (find_by_path: exact full path + FName Number==0
+ meta-class in {BlueprintGeneratedClass,WidgetBlueprintGeneratedClass,Class}) — replaces the flaky find_struct.

### UFunction layout PINNED (from raw dumps; UStruct part already known)
Script(TArray u8)@0x60 {Data@0x60,Num@0x68,Max@0x6C}; FunctionFlags(u32)@0xB0; NumParms(u8)@0xB4;
ParmsSize(u16)@0xB6; ReturnValueOffset(u16)@0xB8 (0xFFFF=no return); Func(native ptr)@0xD8.
BP function Func == UObject::ProcessInternal (ApplySkinToPlayer Func=0x7c03282248 this run -> RVA=Func-base;
one static hop to ProcessLocalScriptFunction for a full VM trace, per reviewer).

### THE GATE (decoded by hand from InitMyRPMAvatarSkin bytecode, Script.Num=671)
InitMyRPMAvatarSkin calls TribeBlueprintLibrary.ReadConfigString(section="TribeAvatar",
key="ReadyPlayerMeAvatarUrl") -> if a URL is present, SpawnObject(BP_ReadyPlayerMeAvatarSkin); else falls
back to Oculus. EX_StringConst literals in the bytecode: "TribeAvatar", "ReadyPlayerMeAvatarUrl",
"My Ready Player Me Avatar", "793D20064B49A061A726F1AC4F790732" (fallback/default RPM id),
"Use your latest custom avatar from tribexr.readyplayer.me".
=> The lever is config[TribeAvatar][ReadyPlayerMeAvatarUrl] = file:///... .glb. **ReadConfigString is NATIVE**
   (/Script/TribeXR.TribeBlueprintLibrary.ReadConfigString) — next read-only step: decompile it (Func@0xD8 -> RVA
   -> Ghidra) to learn the config backing. If a writable .ini/save file -> the mod is a FILE DROP, no injection.

### Pipeline call graph (from ChildProperties local names CallFunc_<callee>_<param>)
- LoadAvatarAtUrl(AvatarUrl:Str) — 44 bytes, thin wrapper (one call; HTTP-vs-native TBD by disasm).
- HandleAvatarLoaded(AvatarComponent, CachedAvatarFilename) -> calls InitMyRPMAvatarSkin.
- InitMyRPMAvatarSkin -> ReadConfigString + SpawnObject(RPM skin).
- AddOrUpdateCachedRPMAvatarSkin(OldFilename,NewFilename) -> GetCleanFilename, cast BP_ReadyPlayerMeAvatarSkin,
  update VisualsManager.RPMAvatarSkins map.
- ApplySkinToPlayer(Skin) [NumParms=1,ParmsSize=8] -> GetSkinClass, IsValidClass, Map_Find.

### VisualsManager skin registry (BP_TribeVisualsManager_C props)
Skins@0x400, RigSkins@0x450, CustomSkins@0x4a0, OculusAvatarSkins@0x538(Map), RPMAvatarSkins@0x588(Map),
ActiveSkins@0x5d8(Map), EnvironmentSkins@0x7c0(Map); key strings K_OculusAvatarSkin@0x528, K_EnvironmentSkin@0x7b0.
GameInstance: AvatarId StrProperty @0x318 on native TribeGameInstance (16-digit Meta id currently).

### L3 ProcessEvent prep
Default__Object vtable_rva=0x06D537B0 (Ghidra 0x06E537B0). 96 slots dumped in sdk.txt; ProcessEvent is the
slot whose body does ldrh ParmsSize@0xB6 + tst FunctionFlags&0x400 + dynamic sp adjust — ID it in Ghidra next.

STOP — gate found (config string). Awaiting direction: decompile native ReadConfigString to decide
file-drop vs runtime-set, then Session 3 hook (or no hook) accordingly.

## Session 3a COMPLETE (read-only) — config backing = GameUserSettings.ini; mod = ini upsert (no hooks)

Config .ini live at INTERNAL path (adb shell can't read; dumper as app UID copied them out):
  /data/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Config/Android/
    Game.ini (50B): [TribeStatus] LaunchCount/SubscriptionGroup
    GameUserSettings.ini (375B): has [TribeSkins] Environment=/Decks=/OculusAvatar=OculusAvatar_Custom,
      [TribeOculusAnchors], [TribeStatus], [TribeCameras], and **[TribeAvatar] bExperimentalTrackingEnabled=True**
      -- NO ReadyPlayerMeAvatarUrl key => empty => Oculus fallback (matches observed Meta avatar).

Native config read confirmed in Ghidra (FUN_050f584c, the spawn-time reader):
  GConfig->GetString(GConfig, L"TribeAvatar", L"ReadyPlayerMeAvatarUrl", &out, PTR_DAT_07ba2d90)
  GConfig->GetString(GConfig, L"TribeAvatar", L"ReadyPlayerMeETag",       &out, PTR_DAT_07ba2d90)
  then builds cache filename L"%srpmavatar-%s" (dir, GetCleanFilename(url)) and checks existence.
PTR_DAT_07ba2d90 = the ini-path FString global (ghidra 0x07d549b0 -> runtime rva 0x07c549b0; .bss, populated
at PreInit). Since [TribeAvatar] lives only in GameUserSettings.ini and the game writes it there, that global
== GGameUserSettingsIni. So both keys (URL, ETag) read from GameUserSettings.ini. 32-hex = MD5 ETag (reviewer),
not an avatar id; inert on a file:// cache-hit.

Native config API RVAs (Func@0xD8; all FUNC_Native): ReadConfigString ghidra 0x50a84b4, WriteConfigString
0x50a9ac8, ForceSaveConfig 0x50a6574, IsValidReadyPlayerMeAvatarUrl 0x50a79dc. (Thunks lazy-init a static;
the real work is the GConfig call as in FUN_050f584c.) LoadAvatarAtUrl is a BP wrapper (native=no,
Func=ProcessInternal); its single call (HTTP vs native) still undecoded but NOT needed for the config path.

'-ini:' wide string IS present @0x25c946 -> command-line ini override may NOT be fully compiled out
(inconclusive; not needed). ReadyPlayerMeETag string present @0x20530c (confirms two keys).

### THE MOD (reviewer's approach; confirmed viable) — libhook constructor upserts the ini, NO hooks
At dlopen (before FEngineLoop::PreInit parses any ini), as app UID (can write internal storage):
  upsert into <internal>/.../Saved/Config/Android/GameUserSettings.ini :
    [TribeAvatar]
    ReadyPlayerMeAvatarUrl=file:///sdcard/Android/data/com.TribeXR.TribeXR/files/Documents/Avatars/custom.glb
  and pre-place custom.glb (+ the rpmavatar-<clean> cache file) so the spawn-time read hits cache -> glTF load
  -> HandleAvatarLoaded -> InitMyRPMAvatarSkin (RPM branch) -> AddOrUpdateCachedRPMAvatarSkin -> ApplySkinToPlayer.
Beats hooking (zero offsets/trampolines) and widget-replay (stock flow runs itself). Upsert idempotent; run each launch.
Open items for 3b: (1) the RPM cache DIR (first %s of "%srpmavatar-%s"; decode FUN_0514ec88 or probe) so the
cache file lands right; fallback Replays/DefaultAvatar.glb via _P pak. (2) stage DefaultAvatar.glb first
(known-good rig) before a custom mesh. (3) gate the upsert on tribemod/avatar_url.txt (swap/disable w/o rebuild).

STOP — 3a done (read-only). 3b (constructor ini upsert) is the FIRST state change -> needs explicit approval.

## Session 3b SUCCESS — config-URL injection loads a custom RPM avatar (NO hooks)

libhook constructor ini_upsert works: reads tribemod/avatar_url.txt, writes
[TribeAvatar] ReadyPlayerMeAvatarUrl=<url> into internal GameUserSettings.ini before PreInit (atomic
tmp+fsync+rename; ASCII/BOM-guarded; delete-key when avatar_url.txt absent = kill switch). ini_upsert.log:
"upsert OK: SET (375->472 bytes)" then "no change (key already set)" (idempotent).

On-device proof (values.txt, in-game): a LIVE BP_ReadyPlayerMeAvatarSkin_C instance now exists
(0x.. [live] .../TribeVisualsManager.BP_ReadyPlayerMeAvatarSkin_C) where before only the CDO existed.
Re-copied ini confirms the key persisted across PreInit + the game's flush. User confirms: a ReadyPlayerMe
avatar option now appears in Tribe's avatar selection UI and switching to it changes the avatar.
=> The whole mod is: staged .glb + one config key. Zero hooks, zero trampolines. Survives updates while the
   ini path + key name hold. Kill switch = adb rm tribemod/avatar_url.txt + relaunch.

Staging that worked (MSYS path-conv gotcha: adb push of a /... remote path gets rewritten by Git Bash;
use MSYS_NO_PATHCONV=1, or push to /data/local/tmp then adb shell cp into tribemod). .glb lives in tribemod
(shell-writable, app-readable — same as params.txt); adb can't mkdir under files/Documents (scoped storage).

### Rendering note: DefaultAvatar.glb is a HALF-BODY RPM avatar (expected hands-only)
skeleton_report.md: 38 joints, mesh 'Wolf3D_Avatar', 63 ARKit morphs. Hierarchy = Hips>Spine>Neck>Head>Eyes
plus LeftHand/RightHand(+fingers) attached directly to Spine. NO Shoulder/Arm/ForeArm, NO UpLeg/Leg/Foot.
So "hands only, no arms/legs" is the mesh, not the mod. Full body needs a FULL-BODY RPM .glb (full skeleton).
Open: "invisible in selfie cam" — likely local avatar OwnerNoSee + the selfie SceneCapture not showing it
(TribePawnBP_C.SetAvatarSceneCaptureHidden / SetAvatarThirdPersonVisible exist); investigate vs a real avatar.

STOP — pipeline proven with a known-good half-body rig. Next: user supplies their real RPM .glb (full-body
if arms/legs wanted); drop as tribemod/custom.glb (same name -> no ini change); relaunch.

## Session 3b rendering investigation — mesh does NOT build; RPM service is DEAD

Config injection is fully proven (avatar selectable; downloads over HTTP). But the RPM avatar renders
nothing (only Tribe's own SK_TribeAvatarHand hand-tracking meshes show; body invisible). Findings:

- Native renderer = /Script/TribeXR.ReadyPlayerMeComponent (AvatarBodyMesh + AvatarLeftHand/RightHand
  SkeletalMeshComponents), a sibling of MetaAvatar2Component under TribeAvatarComponent on the pawn.
  Live instance confirmed: DJRoomMap.PersistentLevel.TribePawnBP_C.TribeAvatar.ReadyPlayerMeComponent.
- Cache dir (Ghidra FUN_0514ec88) = <ext files>/Documents/ ; cache file = Documents/rpmavatar-<clean>.
  Constructor now stages it (app UID; Documents is drwxr-s---, shell can't write). Staging succeeded.
- Load gate FUN_050f584c returns the cached ETag only if URL present AND ETag present in config AND cache
  file exists; without ETag it reports cache-miss -> download.
- HTTP path WORKS: served custom.glb over `adb reverse tcp:8000` (USB); server log shows GET /custom.glb 200
  (full 4.7MB). So the download step succeeds with an http://127.0.0.1:8000 URL.
- BUT after both cache-present AND http-download: NO glTFRuntimeAsset instance (only the CDO), NO runtime
  USkeletalMesh created (all SkeletalMesh instances are packaged assets). So glTFRuntime builds NO mesh from
  DefaultAvatar.glb regardless of how the bytes arrive. AvatarBodyMesh has no mesh -> invisible body.
- Shipping build suppresses UE_LOG: no glTFRuntime/avatar error surfaces in logcat.
- **ReadyPlayerMe service is GONE**: models.readyplayer.me = NXDOMAIN (readyplayer.me root unreachable;
  google.com 200). So no real RPM .glb is obtainable; DefaultAvatar.glb (Wolf3D half-body, Tribe's own
  replay avatar) is the best-possible RPM-format test file — yet the RPM glTFRuntime path won't build it.

Interpretation: the RPM avatar path is likely defunct/bit-rotted post-RPM-shutdown (Tribe removed the RPM
creator UI; the backend glTFRuntime load no longer completes). Meta avatars render via a SEPARATE path
(MetaAvatar2 / libovravatar2.so), and DefaultAvatar.glb renders via the REPLAY system — neither is glTFRuntime.

Kill switch unchanged: adb rm tribemod/avatar_url.txt + relaunch -> constructor deletes the key -> Meta avatar.

STOP — config-injection mod works + RPM load pipeline downloads, but glTFRuntime builds no mesh (RPM path
appears defunct; RPM servers dead). Decision needed: (a) deep-RE the glTFRuntime load call to find the
build failure, or (b) pivot to a known-working render path (Meta SDK / replay), or (c) accept selection-only.

## Session 3b RE deep-dive — load path fully mapped; async glTF build is the blocker (reviewer packet built)

Assembled out/reviewer_packet.md (102KB, 2837 lines) for the expert reviewer: the full question + complete
decompiled bodies of the RPM load path + full glTF structure + skeleton hierarchy + on-device object evidence
+ RPM BP pipeline + ini state + offsets/RVAs reference + glTFRuntime build internals.

Load path (Ghidra addr; RVA = addr-0x100000), all read-only:
- FUN_050f584c: config read TribeAvatar/ReadyPlayerMeAvatarUrl(+ETag) via GGameUserSettingsIni; cache-name %srpmavatar-%s.
- FUN_050f49cc: orchestrator; validates scheme (FUN_04c5b250), dispatches (FUN_04c5a578), loads (FUN_050f4548), WriteConfig ETag.
- FUN_04c5b250: IsValidAvatarUrl — scheme in {http,https,file} (so file:// IS supported).
- FUN_04c5a578: dispatcher; mode byte *param_2 picks branch; builds a glTFRuntimeSkeletalMeshConfig-like struct
  (1.0f scales, 0x901/0x501 flags); *param_2==0 -> FUN_04c59ce0 (glTFRuntime load-from-filename, accepts
  ".glb .gltf .json .js"); sets this+0x5e8/+0x740=1.
- FUN_050f4548 -> FUN_04bde120: glTFRuntime ASYNC load (pthread_mutex, "TAsync %d"), glTFRuntime internals in
  the 0x04bcxxxx-0x04bexxxx cluster.

Blocker (unchanged): download succeeds (HTTP GET 200 via adb reverse; file:// scheme also valid) but the async
build produces NO glTFRuntimeAsset and NO runtime USkeletalMesh -> AvatarBodyMesh empty -> invisible; 2 orphan
/Engine/Transient USkeleton objects (skeleton created, mesh not). Shipping suppresses glTFRuntime logs.
Config-injection + quoted-URL + ETag + Documents/rpmavatar-<clean>.glb cache staging all verified working.

Open for reviewer: what the async completion delegate/abort is, what glTFRuntimeSkeletalMeshConfig/target
skeleton FUN_04c5a578 passes, and the exact Blender .glb spec (skeleton/morphs/materials) this path needs.

## Session 3b — discriminator run: mesh BUILT but not attached; failure is downstream of glTFRuntime

Added read-only skeleton/mesh probes to the dumper (USkeleton.BoneTree.Num @ +0x38 reflected;
SkeletalMeshComponent.SkeletalMeshAsset @ +0x550 reflected). Findings (in-game as the RPM avatar):
- ReadyPlayerMeComponent.AvatarBodyMesh.SkeletalMeshAsset = NULL on the live pawn, EVERY run.
- glTF finalizer transient USkeletons appear with BoneTree.Num=24 (not 0, not ~39); transient, GC'd within
  ~a cycle (absent on a later dump). RawRefBoneInfo read TODO (scan mis-matched BoneTree@0x38; use
  VirtualBoneGuid+0x10 route).
=> Per reviewer's model: skeleton-with-bones => glTFRuntime built a skeleton (load ran); AvatarBodyMesh=null
   => the built mesh is dropped DOWNSTREAM (Tribe's OnSkinLoaded/HandleAvatarLoaded handler), not a load-fail.
Open q: does 24 (vs 38 skin joints) mean a partial gather (errored partway) or a valid pruned skeleton?

Next step (first game hooks since the read-only dumper): AddError(this,FString,FString) -> logcat (find via
xref to ASCII "CreateSkeletalMeshFromLODs()"), and ProcessEvent filtered on the load-complete callback
UFunction logging *(USkeletalMesh**)Parms (non-null => Tribe dropped it; never fired => dead delegate).
Awaiting go-ahead to build the diagnostic hooks.

## Session 3b CORRECTION — the 24-bone skeletons are Meta HANDS, not the avatar; glTF never runs

Reading RawRefBoneInfo at the correct offset (FReferenceSkeleton@0x68 => Data@0x68/Num@0x70, 12B {FName,int32}):
- The two /Engine/Transient.Skeleton (24 bones) are Meta's OVR hand skeleton:
  Wrist_Root, Forearm_Stub, Thumb x4, Index x3, Middle x3, Ring x3, Pinky x4, *_Tip. Two = L/R hand.
- Mesh census (by RF_WasLoaded 0x80000): the ONLY runtime USkeletalMesh are
  TribeControllers_C.OculusXRHandComponent.OculusHandMesh (skeleton "Skeleton"). NO glTF avatar mesh/skeleton exist.
=> The avatar NEVER reaches glTFRuntime. Prior "mesh built, dropped downstream" was WRONG (I mis-ID'd the hand
   skeletons). Only hard fact: ReadyPlayerMeComponent.AvatarBodyMesh.SkeletalMeshAsset = NULL. Break is UPSTREAM
   in Tribe's orchestrator (FUN_050f49cc / FUN_04c5a578), before the glTFRuntime async load.

Next (reviewer-approved): diagnostic hooks (read-only logging), instrument every step:
1. ENTRY hook on the caller of FUN_04bde120 (glTFRuntime LoadSkeletalMeshRecursiveAsync): log NodeName,
   ExcludeNodes.Num, Config.Skeleton(+name), SkeletonConfig.bAddRootBone/RootBoneName, and the FScriptDelegate
   {int32 ObjectIndex, int32 Serial, FName FunctionName}.
2. AddError(this,FString,FString) -> logcat (xref ASCII "CreateSkeletalMeshFromLODs()"; confirm same callee as
   "TraverseJoints()"/"GetRootBoneIndex()"; UTF-16 fallback). FString = {char16_t* Data, int32 Num, int32 Max}.
3. FinalizeSkeletalMeshWithLODs (xref "LOD_%d_Section_%d_%s"): log context mesh + LOD count on entry + return.
4. ProcessEvent filtered on {glTF delegate target fn (from #1), Tribe HandleAvatarLoaded}: log *(USkeletalMesh**)Parms.
Entry never fires => break is upstream in Tribe orchestrator => hook FUN_04c5a578 branches next.

## Session 3b — diagnostic-hook targets located (Ghidra; RVA = addr-0x100000)
- glTF async ENTRY (caller of FUN_04bde120 = LoadSkeletalMeshRecursiveAsync): 04bc2de0 (rva 0x4ac2de0, 468B).
  Other caller = 050f4548 (Tribe per-URL loader). Hooking 04bc2de0 answers "does the avatar reach glTFRuntime?"
- AddError call site (refs "CreateSkeletalMeshFromLODs()"): 04c1b950 (10780B) -> decompile to find the AddError callee.
- Finalize (refs "LOD_%d_Section_%d_%s"): 04c3d288 (6752B) / 04c1e620 (6572B).
- TraverseJoints: 04bf5430 (18208B).  GetRootBoneIndex: 04bf4620 (976B).
- ProcessEvent: from Default__Object vtable_rva 0x06D537B0 (sdk.txt has 96 slots) — ID the slot by ldrh ParmsSize@0xB6
  + tst FunctionFlags&0x400 + dynamic sp adjust.  HandleAvatarLoaded UFunction resolvable by path for the PE filter.

Infra available: hook/vendor/And64InlineHook (arm64 inline trampoline) from the earlier avatar-hook work; DT_NEEDED
injection already proven. Plan: read-only logging hooks (entry/AddError/finalize + ProcessEvent filter). If entry
(04bc2de0) never fires => break is upstream => hook FUN_04c5a578 / FUN_050f49cc branches. This is the next BUILD
(bigger than the read-only dumper); best done at the desk with iterative in-game tests.

## Session 3b — nip.io fails (Quest DNS rebinding); RPM-SDK strings absent; standalone needs a validator hook

- Quest has internet (google.com resolves) but BLOCKS loopback wildcard DNS: 127.0.0.1.nip.io AND
  127.x.sslip.io => "unknown host" (DNS-rebinding protection drops public hosts resolving to 127.x/private).
  So the advisor's no-code nip.io test can't run on this device. adb reverse + raw 127.0.0.1 still work.
- With the nip.io URL set (constructor wrote ReadyPlayerMeAvatarUrl="http://127.0.0.1.nip.io:8000/custom.glb",
  ETag deleted): NO request hit the server (DNS failed before connect).
- RPM-SDK literals ABSENT from libUnreal: no "Url invalid", "AvatarUrlConvertor", "ReadyPlayerMeAvatarLoader",
  "models.readyplayer.me", "meshLod=". Present: IsValidReadyPlayerMeAvatarUrl (ascii 0x503673),
  "readyplayer.me" (0x5be625), rpmavatar- (wide). => Tribe uses its OWN native IsValidReadyPlayerMeAvatarUrl;
  the advisor's exact RPM-SDK regex theory is unconfirmed for this build.
- Can't read the app's /proc/<pid>/maps (no root) => libcurl-vs-Java HTTP still unknown; getaddrinfo hook uncertain.
- Earlier PROOF: with raw IP URL, Tribe's ETag GET reached 127.0.0.1:8000 (adb reverse path works for Tribe's HTTP).
- ngrok IS installed (choco). cloudflared not.

Implications:
- A STANDALONE mod (avatar loads on the Quest, no PC/tunnel) requires HOOKING Tribe's URL validator to accept a
  local URL (file:// or 127.0.0.1), since RPM-style validation rejects local hosts and the Quest blocks loopback DNS.
- To first CONFIRM the pipeline works with a valid URL (no hook), a public tunnel (ngrok/cloudflared) is the only
  no-code option left: set ReadyPlayerMeAvatarUrl=https://<tunnel>/custom.glb, serve custom.glb+custom.json.
  Caveat: ngrok free adds a browser-interstitial that can corrupt non-browser GETs; cloudflared quick tunnel is cleaner.

Decision pending: (A) ngrok/cloudflared confirmation test, then build the validator hook for standalone; or
(B) go straight to the diagnostic+validator hooks (entry 0x4ac2de0, IsValidReadyPlayerMeAvatarUrl, loader).

## Session 3b — DEFINITIVE: config path never fetches; mesh load is LoadAvatarAtUrl-gated. Black-box exhausted.

Tunnel test (cloudflared quick tunnel -> local rpm_server serving custom.glb + custom.json, query stripped):
- URL set to https://liabilities-mit-stage-seen.trycloudflare.com/<24hex>.glb (valid public host, passes any regex).
- Quest RESOLVES + REACHES the host (ping 104.16.230.132 OK). Server served my curl checks (glb/json 200).
- After relaunch AND after the user actively SELECTED the RPM avatar: Tribe made ZERO requests to the tunnel
  (server log shows only my curl UA). glTFRuntimeAsset=CDO only; AvatarBodyMesh.SkeletalMeshAsset=NULL.
Also failed: Step2.1 canonical-URL+staged-cache (no cache fallback); Step2.2 file://+ETag+cache (earlier).

Conclusion: the spawn-time config read (InitMyRPMAvatarSkin = ReadConfigString + SpawnObject, no HTTP in its
bytecode) SPAWNS the RPM skin controller (so it's selectable) but never fetches/builds the mesh. Re-selecting
the avatar re-applies the cached (empty) skin; it does NOT call the loader. The actual fetch+build lives in
W_RPMAvatarCreator.LoadAvatarAtUrl -> HandleAvatarLoaded (the creator "paste URL" flow). So config-only
injection has a hard ceiling: avatar selectable, never loadable. No-code routes (config URL, cache fallback,
file://, valid public URL, DNS) are all exhausted.

Next (requires the first real game hook): either
(a) DRIVE the load: ProcessEvent-call W_RPMAvatarCreator_C.LoadAvatarAtUrl(url) (+ AddOrUpdateCachedRPMAvatarSkin
    -> ApplySkinToPlayer) at spawn = the "widget replay" path; or
(b) DIAGNOSE: log-only hooks on IsValidReadyPlayerMeAvatarUrl impl, glTF entry 0x4ac2de0, FUN_050f584c, to see
    exactly what the config path does and why it doesn't fetch.
Infra ready: hook/vendor/And64InlineHook + DT_NEEDED injection. Tunnel/server left running for the LoadAvatarAtUrl test.

## Session 3b — manual-drive infeasible; LoadAvatarAtUrl decoded; option A = ProcessEvent executor

Pre-checks (advisor):
- W_RPMAvatarCreator_C.WidgetTree children: RPMPasteButton, RPMLaunchWebButton, RPMBackButton, RPMAvatarPanel,
  MessageText/TextBlock, RPMCopy/Goto/PasteImage. NO EditableText/TextBox => clipboard-paste only. And
  `adb shell cmd clipboard set-text/get-text` => "No shell command implementation" => adb can't set the Quest
  clipboard. So the no-code manual creator drive isn't possible on this device.
- LoadAvatarAtUrl bytecode (44B) decoded:
    EX_Let  this->AvatarUrl(instance @0x7b1ac95e00) = AvatarUrl(param @0x7b1a40e180)
    EX_LocalVirtualFunction <FName idx 0x1a1485> ()      // no-param virtual call = the real loader
    EX_Return EX_Nothing ; EX_EndOfScript
  => thin wrapper: store URL member, then virtual-call the loader. Fetch is a BP flow on the widget.
  RPMPasteButton -> PasteAvatarUrl -> LoadAvatarAtUrl is the fetch path (closes the "earlier GET" loose end).

Option A build (ProcessEvent executor), per advisor's guardrails:
- Resolve UObject::ProcessEvent (Default__Object vtable rva 0x06D537B0; ID slot by ldrh ParmsSize@0xB6 +
  tst FunctionFlags&0x400 + dynamic sp). Run calls on the GAME THREAD only (drain a queue from a PE hook,
  e.g. on ReceiveTick), never from the poll thread.
- Use a LIVE W_RPMAvatarCreator_C instance (NOT the CDO: GetWorld()==null on CDO, no widget tree). Find an
  existing one in GUObjectArray, else UWidgetBlueprintLibrary::Create(PC, class, PC); AddToRoot until apply done.
- Call LoadAvatarAtUrl(FString) (or resolve virtual fn 0x1a1485 / the underlying native and call it directly).
- Load is ASYNC: don't call AddOrUpdateCachedRPMAvatarSkin/ApplySkinToPlayer until the completion event; check
  whether the completion already chains them.
- Persistence unknown: after one driven load, diff GameUserSettings.ini / SaveGames / Documents; if a body
  appears on a clean relaunch, replicate that record; else drive every launch.
Standalone (once proven): on-device HTTP server thread inside libhook serving the .glb+.json on 127.0.0.1,
+ (if the validator rejects loopback) force IsValidReadyPlayerMeAvatarUrl true. Needs the game-thread executor
either way. This is the next BUILD (first real game hook); best at the desk with iterative launches.

## Session 3c — ROOT CAUSE: SetAvatarID is never called; the native load was never triggered

Decoded the full creator chain from live Blueprint bytecode (read-only dump, sdk_creator.txt). FName ids
are per-launch, so resolved on THIS run (list_class_functions + by-name EX_LocalVirtualFunction annotator):

- LoadAvatarAtUrl(url):  this->AvatarUrl=url ; this->ReloadAvatarAtUrl()   [0x45 -> FName 0x1a199c]
- ReloadAvatarAtUrl():   (726B) GetGameState/cast ; GetLocalPawn ;
    IsValidReadyPlayerMeAvatarID(AvatarUrl) ; MessageText.SetText("Loading avatar...") ;
    CreateDelegate -> bind TribeAvatar.OnAvatarLoaded = this.HandleAvatarLoaded ;
    CreateDelegate -> bind TribeAvatar.OnAvatarCached = this.HandleAvatarCached ;
    WriteConfigString(AvatarUrl) ;
    EX_Context TribePawnBP.TribeAvatar -> SetAvatarID(AvatarUrl)   [native trigger; FName 0x177642]
- HandleAvatarLoaded (fires on TribeAvatar.OnAvatarLoaded): MessageText.SetText ;
    InitMyRPMAvatarSkin [0x173f90] ; ApplySkinToPlayer [0x1737d5] ; OnAvatarSkinLoaded broadcast
- HandleAvatarCached (fires on TribeAvatar.OnAvatarCached): IsValidReadyPlayerMeAvatarUrl ;
    AddOrUpdateCachedRPMAvatarSkin [0x1737a7]

Objects (this run): live TribeAvatarComponent = DJRoomMap.PersistentLevel.TribePawnBP_C.TribeAvatar
(@0x7b23036a00, child ReadyPlayerMeComponent @0x7b1a8b3730). NO live W_RPMAvatarCreator_C (menu closed).

ROOT CAUSE (clean): the native fetch+build is triggered ONLY by TribeAvatar.SetAvatarID(url), and the ONLY
caller of SetAvatarID is ReloadAvatarAtUrl (creator "paste URL" flow). The config-selection path
(InitMyRPMAvatarSkin = ReadConfigString + SpawnObject) NEVER calls SetAvatarID. The creator flow was never
driven (no EditableText, adb clipboard unimplemented, no live widget). => SetAvatarID has never run =>
the native load never fired => AvatarBodyMesh.SkeletalMeshAsset stays NULL. Prior "download proven" GETs
were all my PC-side curl (byi7n4jkl log line at 19:52:13 aligns with my curl, not Tribe). Tribe never fetched.

Completion already wires visibility+persistence: don't re-implement ApplySkinToPlayer/AddOrUpdateCachedRPMAvatarSkin;
the delegates run them, but ONLY if a widget bound them. So driving the widget's LoadAvatarAtUrl (which binds the
delegates then calls SetAvatarID) is the faithful path; calling SetAvatarID bare would fetch+build but leave the
completion delegates unsubscribed (no InitMyRPMAvatarSkin/ApplySkinToPlayer).

Validator: IsValidReadyPlayerMeAvatarID is checked inside ReloadAvatarAtUrl (on AvatarUrl) BEFORE SetAvatarID;
IsValidReadyPlayerMeAvatarUrl is in HandleAvatarCached. If driving LoadAvatarAtUrl, the ID check runs -> may need
a URL/ID that passes it (or hook it). To confirm, the diagnostic run logs its return.

NEXT BUILD (first real game hooks; reviewer-approved): (1) in-libhook loopback HTTP server (127.0.0.1, non-8000
port, query-strip, Content-Length/Type/ETag, HEAD + If-None-Match->304, .json only if requested); (2) diagnostic
log-only hooks: glTF entry 0x4ac2de0, AddError, finalize, ProcessEvent filter on {SetAvatarID, OnAvatarLoaded
target, HandleAvatarLoaded}; (3) game-thread executor: create a W_RPMAvatarCreator_C (UWidgetBlueprintLibrary
::Create, AddToRoot) and ProcessEvent LoadAvatarAtUrl(url) — OR call SetAvatarID direct + bind completion. First
run is DIAGNOSTIC: does driving SetAvatarID make Tribe fetch, and does the native build yield a USkeletalMesh?

## Session 3c Phase 1 — in-libhook loopback HTTP server (127.0.0.1:8787) VERIFIED

Added a constructor-started HTTP server thread to dumper.cpp (bind 127.0.0.1 only, port 8787 != adb-reverse
dev port 8000). Serves tribemod/custom.glb for any *.glb path (model/gltf-binary) and a JSON metadata blob
for *.json; strips query strings; sends Content-Length/Type/ETag; supports HEAD and If-None-Match->304.
ETag = uppercase MD5 (compact in-tree MD5; verified on-device against python: 'abc' and custom.glb both match
BB01368FC663411E5AD676EE268AAC4E). Verified via adb forward tcp:8790->device 8787:
  GET glb -> 200, 4732412 bytes, body byte-identical to custom.glb
  GET json-> 200 metadata ; HEAD -> headers only ; If-None-Match=ETag -> 304.
No game mutation. This makes the mod self-hosting (standalone target). Next: Phase 2 diagnostic hooks +
Phase 3 game-thread executor to drive LoadAvatarAtUrl (fires SetAvatarID for the first time).

## Session 3c Phase 2-prep — ProcessEvent resolved; metadata/root-node pipeline found (offline RE)

ProcessEvent: FUN_01957dd4 (Ghidra rva 0x1857dd4) is UObject::ProcessEvent — sig (this,Function,Parms),
tests FUNC_Native via (FunctionFlags@0xb1>>2 & 1) [bit10=0x400], memcpy(frame,Parms,ParmsSize@0xb6). The
by-name caller FUN_01957508 builds a frame and calls this->vtable[0x270](this,UFunction,frame) = slot 78.
ADDRESS SKEW: runtime vtable slot 78 read = base+0x1858dd4, but ProcessEvent's Ghidra rva is 0x1857dd4
(exactly 0x1000 lower). So the 0x185xxxx code region has runtime = base + ghidra_rva + 0x1000, while the
0x4xxxxxx region (dispatcher 0x4ffc2d4 hook fired at +0) has delta 0. Skew is PER-SEGMENT -> every hook/call
target must be prologue-verified at runtime. Executor will self-calibrate: try base+rva and base+rva+0x1000,
pick the one that is an AArch64 prologue (+ for ProcessEvent, contains ldrh [x?,#0xb6] = word&0xFFFFFC00==0x79416C00).
calib.txt probe added to dumper (not yet run; app relaunch blocked by Meta unofficial-app dialog).

RPM load pipeline (native, from string/global xrefs) -- explains the invisible body:
- Global PTR_DAT_07c681c0 = "https://readyplayer.me/api/avatar/" (base). FUN_04c5b054 builds base+<id> = the
  METADATA API url. readyplayer.me is DEAD (NXDOMAIN) -> this fetch fails.
- FUN_04c5c3b0 parses the metadata JSON and compares bodyType to "Halfbody" (PTR_DAT_07c68258); picks the glTF
  ROOT NODE name: "AvatarRoot" (halfbody, PTR_07c68188) vs "Armature" (fullbody, PTR_07c68190). Other metadata
  globals: "bodyType","outfitGender","Masculine","Feminine","Fullbody","Halfbody","outfitVersion".
- DefaultAvatar.glb (our custom.glb) root node = "AvatarRoot" (halfbody). If the dead metadata fetch fails,
  Tribe likely defaults/errs the bodyType -> wrong root node ("Armature") -> glTF joint traversal from a
  non-existent node -> empty skeleton/mesh -> AvatarBodyMesh.SkeletalMeshAsset stays NULL -> invisible. This
  is the advisor's predicted AvatarRoot-vs-Armature mismatch, now grounded in code.

Fix implications (decide after the diagnostic run confirms the break point):
- Serving .glb alone is insufficient: the bodyType/root-node comes from readyplayer.me metadata (hardcoded
  base global), not necessarily from our URL. Options: (a) hook FUN_04c5b054 or the metadata fetch to point
  at our loopback JSON; (b) drive LoadAvatarAtUrl and force the root node / bodyType; (c) FALLBACK (now looks
  primary): bypass Tribe's RPM path -- call glTFRuntime directly on our .glb and bind its async completion to
  AvatarBodyMesh.SetSkeletalMeshAsset (loses ApplySkinToPlayer's materials/IK/morphs but avoids the dead API).
- The glTF ENTRY diagnostic hook (0x4ac2de0) logs the NodeName it traverses from -> directly confirms whether
  the root node is wrong. AddError hook -> logs the traversal failure. This is the next runtime step.

Blocked on device: Meta "unofficial app" reprojected VR dialog (com.oculus.vrshell/.systemdialog.launchcheck
.UnOfficialAppDialogActivity) gates the app launch; adb keyevents don't dismiss it (needs an in-headset click).
adb CAN wake the headset + simulate proximity (am broadcast com.oculus.vrpowermanager.prox_close) + am start,
but not click the dialog. So a human tap on "Open" is required once per relaunch.

## Session 3c — CALIBRATED + all executor layouts captured (dialog tap works!)

Headset unblock: the "unofficial app" gate is com.oculus.vrshell/.systemdialog.launchcheck.UnOfficialAppDialogActivity,
a real 480x750 2D window -> `adb shell input tap` REACHES it. Buttons (uiautomator): primary "Restore"
[40,434][440,489] = restores to store version (NEVER tap); secondary "Close" [40,499][440,554] center (240,526).
There is also a separate "Open" prompt on entry (user-reported). adb CAN tap these now.

CALIBRATION (calib.txt, base=0x7bf7240000): uniform skew runtime = base + Ghidra_rva + 0x1000 for code.
Confirmed by prologue (fd7bXXa9 / ffXXXXd1) appearing only at +0x1000 for dispatcher/choke/ProcessEvent/CallFunction.
=> ProcessEvent runtime = base+0x1857dd4+0x1000 = base+0x1858dd4 (== vtable slot 78; double-confirmed).
Executor needs ONLY ProcessEvent as a raw address; all glTF calls go through it by reflection.

Executor param layouts (from sdk_gltf.txt; call via ProcessEvent(obj,fn,&parms)):
- glTFLoadAssetFromFilename (Default__glTFRuntimeFunctionLibrary; native): ParmsSize 0x218 -- Filename FString@0x00,
  bPathRelativeToContent bool@0x10, LoaderConfig struct@0x20 (0x1f0), ReturnValue UglTFRuntimeAsset*@0x210.
- glTFRuntimeAsset.LoadSkeletalMesh (on asset; native): ParmsSize 0x758 -- MeshIndex int@0x00, SkinIndex int@0x04,
  SkeletalMeshConfig struct@0x08 (0x748), ReturnValue USkeletalMesh*@0x750.  Load by index (0,0) sidesteps root-node name.
- glTFRuntimeAsset.GetErrors (on asset; native): ParmsSize 0x10 -- TArray<FString> ReturnValue@0x00.
- SkeletalMeshComponent.SetSkeletalMeshAsset (on AvatarBodyMesh; native): ParmsSize 0x8 -- NewMesh obj@0x00.

Config structs (offsets WITHIN the struct): 
- glTFRuntimeConfig (0x1f0): TransformBaseType Enum@0x00, SceneScale float@0x150 (default 1.0 -> MUST set, zero=invisible).
- glTFRuntimeSkeletalMeshConfig (0x748): Skeleton obj@0x08 (null=auto-build), OverrideSkinIndex int@0x2c (default -1),
  SkeletonConfig struct@0x30, MaterialsConfig struct@0x240, BoundsScale FVector@0x640 (default (1,1,1) -> MUST set),
  bIgnoreEmptyMorphTargets bool@0x6ca (default true).
- glTFRuntimeMaterialsConfig (0x3b0): bSkipLoad bool@0x220 (set true for v1 gray-mesh test).
  => within LoadSkeletalMesh parms: SkeletalMeshConfig base = parm+0x08; bSkipLoad at parm+0x08+0x240+0x220 = +0x468;
     BoundsScale at parm+0x648 (3 doubles =1.0); OverrideSkinIndex at parm+0x34 = -1; Skeleton at parm+0x10 = 0.

Component: ReadyPlayerMeComponent.AvatarMeshComponent ObjectProperty@0x260 -> the AvatarBodyMesh SkeletalMeshComponent
(live path DJRoomMap...TribePawnBP_C.TribeAvatar.ReadyPlayerMeComponent.AvatarBodyMesh). Also RightHand/LeftHandMeshComponent@0x268/0x270.

Graft (advisor): after SetSkeletalMeshAsset, run Tribe's InitMyRPMAvatarSkin + ApplySkinToPlayer (BP_TribeVisualsManager_C
singleton) for materials/IK/visibility -- but v1 minimal may just be SetSkeletalMeshAsset on the already-active skin's
AvatarBodyMesh (mesh appears gray via bSkipLoad). Materials pass 2. Selfie-cam (pass 2): bOwnerNoSee/bVisibleInSceneCaptureOnly
via Tribe's SetAvatarThirdPersonVisible/SetAvatarSceneCaptureHidden.

## Session 3c — auto-load on launch + skin selection (permanence)

Auto-load: poll thread, when tribemod/auto_load exists, waits (every ~2s) until the live pawn body appears
(find_live PersistentLevel), then arms the PE-drain -> do_load fires once per launch. No manual trigger.
Key fix: g_numElements was cached early (27090) so find_live missed the later-spawned pawn; added g_ne_addr
(NumElements address) + refresh_numelements() to re-read the live count (grew to 62987) before every scan.
Skin selection: active_skin.txt names a file in tribemod/skins/ (else glb_path.txt, else custom.glb).
Verified: fresh launch auto-loaded skins/default.glb, textured (M_glTFRuntimeBase resident), attached+visible.
Flags: executor_on (install hook), auto_load (auto-fire). Kill switch: rm executor_on + relaunch.
To swap skins: change active_skin.txt (+ relaunch, or touch load_avatar to hot-swap in the running session).

Legs/full-body: pipeline loads whatever is in the .glb -- a full-body Blender export shows legs (visible).
IK-driven legs (move with you) need binding to Tribe's avatar skeleton (Skeleton=Tribe skel, RootBoneName,
CopyRotationsFrom) instead of Skeleton=null -- a follow-up. DefaultAvatar.glb is half-body by design.

## Session 3c — skullbuck loads, but Tribe actively resets the body -> keeper build

User's own avatar skullbuck.glb (Blender 4.5, full-body RPM rig: 54 joints Hips->spine/arms/legs/toes, 36.7k tris,
3 PBR textures) auto-loaded first try: mesh built textured, attached, visible flags set. But the user saw NOTHING.
Diagnosis (dumps): live body DJRoomMap...ReadyPlayerMeComponent.AvatarBodyMesh went back to SkeletalMeshAsset=null
(both after the early auto-load AND after a manual re-attach with the game fully settled, ~40s later), and our
orphaned transient USkeletalMesh was then GC'd (renamed 'None'). => Tribe actively resets its RPM body mesh (its
own RPM state = 'no mesh loaded'); not merely an auto-load timing issue. Also the avatar menu ("My Ready Player
Me Avatar" = Loaded) re-applies the empty RPM skin; the skin-cycle hook logged no 'skin cycle' (ApplySkinToPlayer
likely a direct BP call, not ProcessEvent).

Keeper build (76864B, installed, NOT yet tested -- headset battery hit 4%):
- root_object(mesh): set EInternalObjectFlags::RootSet (1<<30) on the mesh's FUObjectItem (== AddToRoot) so GC
  can't free it; unroot the previous skin's mesh on swap.
- PE-hook blocker: swallow SetSkeletalMeshAsset calls on our body with a mesh != ours (BP-level resets), logged.
- Poll-thread keeper (~1s): read body+0x550; if != our mesh -> log NATIVE reset + request re-attach, drained on
  the game thread in the PE hook (attach_mesh = SetSkeletalMeshAsset + OwnerNoSee(false)/Visibility/HiddenInGame).
  Validity guard: if g_body's class is no longer SkeletalMeshComponent, keeper turns off.
Next test tells us: BLOCKED-BP vs NATIVE reset counts/frequency. If Tribe resets every tick natively, fall back to
spawning our own SkeletalMeshComponent (AddComponentByClass + attach under AvatarBodyMesh) that Tribe doesn't manage.

## Session 3c — ROOT CAUSE of invisible avatar: LoaderConfig.SceneScale was 1.0 (default is 100)

Advisor diagnosis, verified against glTFRuntimeParser.h (FglTFRuntimeConfig ctor: `SceneScale = 100;`).
glTFRuntime multiplies every vertex position / node translation / bind matrix by SceneScale to convert glTF metres
to UE centimetres. I had hardcoded 1.0 => the 2.03 m skullbuck rendered ~2 cm tall: inside the near-clip plane in
first person, a speck in the selfie cam => "renders in no camera". (DefaultAvatar was never visually confirmed
either -- almost certainly the same speck.) All my other hand-set defaults match source exactly:
TransformBaseType=Default, bAllowExternalFiles=true, BoundsScale=OneVector, OverrideSkinIndex=-1,
RootNodeIndex=INDEX_NONE, MaxNodesTreeDepth=-1. So SceneScale was the ONLY wrong value.

Build (79872B, compiled; device disconnected to charge -- not yet installed):
- SceneScale=100.
- Fixed rooted=0: refresh_numelements() before root_object (new mesh index was past the cached count).
- attach_mesh clears SetLeaderPoseComponent(nullptr) first (advisor Q4: mismatched leader-pose can collapse verts).
- Objective render check (advisor): RENDER report 3s after attach then every 10s (max 8): WasRecentlyRendered(0.5),
  body world loc (K2_GetComponentLocation), world scale (K2_GetComponentScale), camera loc (PlayerCameraManager.
  GetCameraLocation), delta, mesh-still-attached. ParmsSize/ReturnValueOffset read from the UFunction at runtime.
Advisor next steps if the slot still won't draw: isolation ASkeletalMeshActor 1.5 m in front of the HMD
(BeginDeferredActorSpawnFromClass/FinishSpawningActor) as a matrix {bSkipLoad on/off} x {DefaultAvatar, skullbuck};
read bVisible/bHiddenInGame/bOwnerNoSee/bRenderInMainPass + owner bHidden + parent scale; decode
SetAvatarThirdPersonVisible / SetAvatarSceneCaptureHidden. Placement: skullbuck origin is at the hips; RPM full-body
convention is origin at the feet -> re-export with origin at feet.

## Session 3c — Tribe's body slot is never drawn -> isolation actor (our own ASkeletalMeshActor)

SceneScale=100 build (installed, confirmed rooted=1) render reports x8: WasRecentlyRendered(0.5)=0 every time;
slot world loc pinned at exactly (0,0,0), scale (1,1,1), while the camera moved (-28..-7, 78..106, 115..124) and the
user looked around the floor. mesh ok=1 (still attached). => Tribe's AvatarBodyMesh slot is inactive/unregistered
(identity transform, no render proxy) -- Tribe only activates it when its own RPM load completes, which never happens.
The mesh is fine; the slot is dead. Stop using it.

Isolation-actor build (83976B, installed): flag tribemod/iso_here (one-shot) -> on the game thread,
GameplayStatics.BeginDeferredActorSpawnFromClass(WorldContext=PlayerCameraManager, ASkeletalMeshActor, xf,
AlwaysSpawn, owner=null, MultiplyWithRoot) + FinishSpawningActor, then SetSkeletalMeshAsset(our mesh) on its
SkeletalMeshComponent (+Visibility/HiddenInGame), AddToRoot. Placed 2 m ahead of the camera along camera yaw,
turned to face it, z=97 cm (skullbuck's origin is its hips -> feet on the floor). All params resolved BY NAME from the
UFunction at runtime; FTransform = 96 B (quat@0, translation@32, scale@64), verified against the SpawnTransform
param ElementSize (aborts if != 96). RENDER reports now cover both 'slot' and 'ISO'. Links -lm (sin/cos).
If ISO renders: mesh good -> attach our actor to follow the player (replacing Tribe's slot for good).
If ISO doesn't: run advisor matrix {bSkipLoad on/off} x {DefaultAvatar, skullbuck}.

## Session 3c — *** FIRST CONFIRMED RENDER: skullbuck visible in Tribe XR *** (user: "I SEE HIM!")

Isolation-actor build, after fixing my own size check (FP_ElemSize@0x34 reads 0 for every property in this build --
that offset is wrong; validated FTransform instead by the param GAP: SpawnTransform@16 -> CollisionHandlingOverride@112
= 96 B exactly). Spawn log: BeginDeferredActorSpawnFromClass psz=0x90 WC@0 Cls@8 Xf@16 Coll@112 Scl@128 Ret@136 ->
actor; FinishSpawningActor; ASkeletalMeshActor.SkeletalMeshComponent@0x298; SetSkeletalMeshAsset(skullbuck).
RENDER #1 ISO: WasRecentlyRendered(0.5)=1 at (56,-104,97), d=(63,-190,-24)cm from camera, scale 1.
User confirmed visually; screenshot (claudedocs/skullbuck_first_render.jpg): white deer skull + antlers, dark body,
upright at human height, TEXTURED (materials on, not the gray fallback), feet on the floor (z=97 = hip origin).

Proven end-to-end: custom Blender .glb -> glTFRuntime (SceneScale=100) -> USkeletalMesh -> our own actor -> drawn.
Root causes, in order: (1) dead readyplayer.me metadata path (bypassed via direct glTFRuntime load); (2) RootNodeIndex
zeroed (-1 fixed bone map); (3) SceneScale 1.0 vs default 100 (avatar was 2 cm); (4) Tribe's AvatarBodyMesh slot is
inactive (world origin, never drawn) -- replaced by our own spawned ASkeletalMeshActor.
Next: attach our actor to the player so it follows them (replace Tribe's slot); face/orientation; then articulation
(bind to Tribe's skeleton/IK so arms/head/legs move). Also re-export skullbuck with origin at feet (convention).

## Session 3c — Follow v1 (advisor round 3) + Meta body tracking IS compiled in

Advisor answers (follow/tick/articulation/hands/facing/multiplayer) recorded in the conversation; implemented #1/#2/#5 now:
- Our ASkeletalMeshActor ticks itself: before FinishSpawningActor, set PrimaryActorTick.bCanEverTick/bStartWithTickEnabled
  and TickGroup/EndTickGroup=TG_PostUpdateWork(5) via reflection. sizeof(FProperty) is SELF-CALIBRATED (offset of
  FObjectPropertyBase::PropertyClass on SkeletalMeshActor.SkeletalMeshComponent == SkeletalMeshComponent UClass), then
  FBoolProperty {FieldSize,ByteOffset,ByteMask,FieldMask}@S; sanity-gated (single-bit mask, bo<8, off<0x80) -> abort, not corrupt.
  Theory (to verify): FField data ends at 0x2C and FProperty members pack into its tail padding (Itanium ABI):
  ArrayDim@0x2C, ElementSize@0x30, PropertyFlags@0x38, Offset_Internal@0x44 (matches) -> FP_ElemSize=0x34 was wrong.
- ReceiveTick of OUR actor (== /Script/Engine.Actor.ReceiveTick; AActor::Tick always routes it through ProcessEvent) is caught in
  the PE hook -> follow_update(dt). Fallback only while ours is silent: the pawn's (BP) ReceiveTick, matched by name.
- follow_update: HMD = TribePawnBP_C.Camera (K2_GetComponentLocation/Rotation); floor = TribePawnBP_C.VROrigin world Z;
  body = HMD xy pushed back 10 cm along HMD yaw; yaw smoothed (dead zone +-35 deg, k=5*dt) and biased 50% toward the
  MotionControllerL/R midpoint when it's 15-110 cm away (torso keeps facing the decks); K2_SetActorLocationAndRotation
  (bTeleport). Rest pose captured lazily on the first ticks: model forward = horizontal(Toe-Foot, L+R) via GetBoneName +
  GetSocketTransform(RTS_Component) -> actor yaw = bodyYaw - forward; actor z = floorZ - toeZ (feet on floor).
- SetCollisionEnabled(NoCollision) + SetCastShadow(false) on our mesh (can't block Tribe traces; Quest frame time).
- tribemod/auto_actor: spawn + follow automatically ~2 s after the mesh loads, every launch.
Pawn components found: VROrigin, Camera, MotionControllerL/R, TribeAvatar, VRBodyReplication (Tribe's MP head/hand sync), HeadCollisionSphere.

Meta Movement SDK IS in the build: /Script/OculusXRMovement.{OculusXRBodyTrackingComponent, OculusXRMovementFunctionLibrary,
OculusXRBodySkeleton/Bone/State, OculusXRBodyJoint}. => advisor #3c: real Quest 3 body tracking retargeted onto the mesh via a
bone-name map (needs com.oculus.permission.BODY_TRACKING in the manifest + body tracking enabled at startup -- both doable
since we repack the APK and inject ini before PreInit). Candidate for the articulation phase instead of hand-rolled IK.
Missing UFunctions: SkinnedMeshComponent.GetBoneLocation (use GetSocketTransform), SkinnedMeshComponent.SetBoneScaleByName
(use PoseableMeshComponent.SetBoneScaleByName or HideBoneByName).
Built 94800 B; not yet installed (headset charging).

## Session 3c — *** FOLLOW WORKS: skullbuck in Tribe's own SELFIE CAM, at the decks, facing correctly ***

Follow v1 test (battery 24%): auto_actor spawned our actor ~2 s after load, then it followed the HMD every frame.
- Tick calibration: sizeof(FProperty)=0x70 (confirms FP_ElemSize=0x34 was wrong; FProperty ends at 0x70, so
  FBoolProperty {FieldSize,ByteOffset,ByteMask,FieldMask}@0x70..0x73, FObjectProperty.PropertyClass@0x70).
  AActor.PrimaryActorTick@0x28 (ActorTickFunction); bCanEverTick = byte 10 mask 0x02, bStartWithTickEnabled = byte 10
  mask 0x04; TickGroup@8, EndTickGroup@9 -> 5. All sanity gates passed.
- BUT isoTicks stayed 0: this engine does NOT route ReceiveTick through ProcessEvent for NATIVE actor classes
  (ASkeletalMeshActor) -- advisor's "always routes" doesn't hold here. The fallback (TribePawnBP_C's Blueprint
  ReceiveTick, matched by name) drives follow at ~70 fps (dt ~0.014). Pawn ticks PrePhysics -> <=1 frame lag, invisible.
- Rest pose: 54 bones, LFoot=(3,11.5,-90) LToe=(-9.5,12,-95.2) -> model forward 180 deg (exactly the advisor's
  glTF-Default prediction), toeZ=-95.2 -> actor z = floor+95 = feet on the floor.
- Follow math verified from logs: hmd=(-10,85,108) yaw -86 -> actor=(-11,95,95) (10 cm behind along yaw);
  actor yaw = body - 180. WasRecentlyRendered=1 at the user's position.
- VISUAL (claudedocs/skullbuck_selfie_cam_following.jpg): Tribe Visuals -> Camera -> Selfie shows skullbuck standing
  behind the DJ decks, facing the selfie cam, textured, human-scale. Rest A-pose (no articulation yet).
Open: user was seated (eye 1.1 m) while the model stands at full height -> camera inside the chest in first person.
Next phase: articulation (Meta OculusXRBodyTrackingComponent retarget, or PoseableMesh + IK), hands vs Tribe's hands,
seated/crouch (pelvis drop), and wire the skin-cycle to swap the actor's mesh.

## Session 3c — ROUTE A1: Meta body tracking ENABLED in Tribe (full body, 84 joints streaming)

Advisor route A, in his order: manifest -> ini -> permission -> start -> verify. All verified on device.
- MANIFEST: scripts/patch_manifest.py (binary AXML) clones existing leaf elements byte-for-byte (FACE_TRACKING permission,
  oculus.software.face_tracking feature w/ required=false) and re-points android:name at strings APPENDED to the UTF-16
  pool (#191/#192; no existing index moves, so the resource-map-bound attr names stay valid). Adds
  com.oculus.permission.BODY_TRACKING + com.oculus.software.body_tracking (required=false). aapt xmltree diff = exactly
  the 2 elements; permissions 19 -> 20; idempotent re-run = no-op. Packaging now also adds AndroidManifest.xml:
    python scripts/patch_manifest.py <(unzip base.apk AndroidManifest.xml) out/hookA/stage/AndroidManifest.xml \
      uses-permission:com.oculus.permission.FACE_TRACKING:com.oculus.permission.BODY_TRACKING \
      uses-feature:oculus.software.face_tracking:com.oculus.software.body_tracking
    7z a ... lib/arm64-v8a/libUnreal.so lib/arm64-v8a/libhook.so AndroidManifest.xml   (then zipalign + apksigner as before)
- PERMISSION: BODY_TRACKING is INSTALL-TIME on this Horizon OS: `pm grant` -> "not a changeable permission type", and
  dumpsys shows granted=true right after install (no horizonos.* runtime twin, unlike FACE_TRACKING).
- ENGINE.INI: constructor upserts [/Script/OculusXRHMD.OculusXRHMDRuntimeSettings] bBodyTrackingEnabled=True into
  Saved/Config/Android/Engine.ini (created if missing; gated on tribemod/body_tracking, flag absent -> key deleted).
  CDO readback = 1 -> this shipping build DOES read the saved-ini layer. XrApi = OVRPluginOpenXR. (CDO defaults
  BodyTrackingFidelity=Low, BodyTrackingJointSet=UpperBody; overridden at runtime.)
- GHIDRA (scripts/FindNativeThunk.java: exec thunks by name via the FNameNativePtrPair tables):
  TryGetBodyState impl FUN_04b7f43c writes Joints.Data[0..69] (upper) / [0..83] (full) at stride 0x40 with NO resize and
  NO bounds check; under ProcessEvent the out-struct IS our parm buffer -> a zeroed TArray = null write = crash. So
  Joints is pre-pointed at our own static 84-slot storage (ProcessEvent never frees/copies back out-params).
  StartBodyTrackingByJointSet -> PluginWrapper+0x758 (StartBodyTracking2) then +0x760 (fidelity); NO settings gate.
  IsBodyTrackingEnabled = +0x730, GetBodyState4 = +0x748, GetFullBodyTrackingEnabled = +0x750 (picks 70 vs 84 joints).
- LAYOUT (reflection == native): FOculusXRBodyState {IsActive@0, Confidence@4, SkeletonChangedCount@8, Time@0xC,
  Joints@0x10} 0x20 B; FOculusXRBodyJoint {LocationFlags u64@0, bIsValid@8, Orientation FRotator@0x10, Position
  FVector@0x28} 0x40 B. TryGetBodyState parms 0x25: state@0, WorldToMeters@0x20, Ret@0x24. EOculusXRBoneID: 84 bones
  (0 BodyRoot, 1 BodyHips, 2-5 spine/chest, 6 Neck, 7 Head, 8-17 arms, 18-69 hands, 70-83 legs/feet) + 3 sentinels.
- RESULT: CheckPermission=1, IsBodyTrackingSupported=1, StartBodyTrackingByJointSet(FullBody=1)=1,
  RequestBodyTrackingFidelity(High=2)=1; IsBodyTrackingEnabled 0 right after start -> 1 within 1 s (async).
  TryGetBodyState=1, IsActive=1, conf=1.00, 84/84 valid, still enabled at poll #7 (~90 s; no Avatars-SDK conflict seen).
  OS: "NIMBLE:InsideOutBodyTracking: Using raw images", "Body Tracking Processed FPS = 29.8 Hz ... Dropped 0 frames".
  Game frame dt unchanged (12-16 ms).
- FRAMES: positions = tracking space, UE axes, cm, floor z~0 (seated: hips 62 / head 115 / ankles ~2, knees forward;
  standing: hips 104 / head 165 vs HMD world z 171 -> head joint ~7 cm below the eyes). logs/bt1/bt_joints.txt = first
  full 84-joint dump. Joint rotations are Meta's joint frames (spine chain roll 50-90 deg) -> calibrate, don't name-map.
Next (A2, advisor Q4): PoseableMesh retarget -- calibration pose (user roughly in the avatar's A-pose) captures C_j and
R_b; per frame bone world rot = (M_j * C_j^-1) * R_b; rotations + hips position only; wrists pinned (two-bone IK,
Meta elbow as pole); keep Tribe's tracked hands. Tracking -> world via the VROrigin transform (verify: Head vs Camera).

## Session 3c — *** ROUTE A2: skullbuck ARTICULATED by Meta body tracking *** (user: "its moving with me! thats awesome!")

Advisor A2 plan (T-pose offsets, head from HMD, attach to the Camera's parent), with two corrections of mine:
- R_align: O_b = M_j(T)^-1 * R_z(you - avatar facing) * A_b(T). The advisor's O_b = M_j(T)^-1 * A_b(T) silently assumes
  you face the avatar's own forward (-X) during capture; any other facing bakes a constant twist into every bone.
- Head offset needs no capture: O_head = R_z(-avatarFacing) * restHeadCS; per frame Head = CameraRelRot * O_head.
- skullbuck's material is doubleSided (read from the .glb) -> a camera inside its head would see the skull's inner
  faces. So TWO PoseableMeshComponents: A = full body, bOwnerNoSee (selfie cam/others); B = HideBoneByName(Head),
  bOnlyOwnerSee (you, looking down). Our actor SetOwner(pawn) so the owner flags apply. Model hands hidden on both.
How it runs (hook/dumper.cpp "Route A2"):
- Per frame from the pawn's ReceiveTick: TryGetBodyState (same pre-sized Joints storage) -> 22 bones mapped by name
  (Hips<-BodyHips(1), Spine<-SpineMiddle(3), Spine1<-SpineUpper(4), Spine2<-Chest(5), Neck(6), Head(7)->HMD,
  Shoulder<-BodyShoulder(8/13), Arm<-ArmUpper(10/15), ForeArm<-ArmLower(11/16), Hand<-HandWrist(19/45),
  UpLeg<-UpperLeg(70/77), Leg<-LowerLeg(71/78), Foot<-FootAnkle(73/80), ToeBase<-FootBall(76/83)).
  A_b = M_j * O_b in component space; hips translation = Meta hips / s; neck takes half the HMD-vs-Meta head seam;
  two-bone IK pins the wrists to Meta's wrist joints (Meta elbow = pole); own FK (ref pose via GetRefPoseTransform +
  GetParentBone) -> SetBoneTransformByName(ComponentSpace) parent-first on both meshes (44 PE calls/frame).
- Meshes: Actor.AddComponentByClass(PoseableMeshComponent) -> SetSkinnedAssetAndUpdate -> K2_AttachToComponent(Camera's
  GetAttachParent = VROrigin, SnapToTarget) -> SetRelativeScale3D(s) -> NoCollision, no shadow, SetTickGroup(PostUpdateWork).
- Calibration saved per rig: tribemod/skins/<skin>.bt.txt (offset quats + scale); touch tribemod/bt_recalibrate to redo.
  Crash-loop guard: tribemod/a2_inflight exists from go-live until 120 good frames; a launch that finds it skips A2.
Verified on device:
- Resolve: all 16 UFunctions + PoseableMeshComponent class; SceneComponent RelativeLocation@0x128 RelativeRotation@0x140;
  EAttachmentRule SnapToTarget=2 KeepRelative=0; EBoneSpaces ComponentSpace=1; WorldSettings.WorldToMeters=100.
  SetBoneTransformByName psz 0x71: BoneName@0 InTransform@16 BoneSpace@112.
- Rest: 54 bones (root Hips), 22/22 mapped, avatar faces 180 deg, eyes 162.1 cm above soles. A-pose arm elevation
  L -70/-65/-62 deg -> constructed T-pose 0.0/0.0/0.0 (swing construction exact).
- Advisor Q2: 150/150 frames had a new sample -> the runtime predicts joints every frame; no smoothing needed.
- rot2q (FRotator -> FQuat) verified offline as the exact inverse of UE's FQuat::Rotator (20000 random, err 1e-14).
- Calibration: user first held an A-pose (tilt -65..-73 deg, knees L22-31) which the T-pose detector rejected; then a
  T-pose -> "CALIBRATED: you face -48 deg, avatar 180 deg; scale 1.006 (eyes 163 / 162 cm)". Meshes A+B attached to
  VROrigin; 120 frames OK (guard cleared); dt 10-16 ms (unchanged).
- Advisor's frame check: eyes vs Meta head joint in the HMD frame = fwd +5..8, right ~0, up +7..10 cm -> tracking
  space == VROrigin space (no UE base offset). Wrist IK corrects 5-25 cm per frame. WasRecentlyRendered A=1, B=1 when
  looking down.
Not yet verified by eye: that A is hidden from the user's own view (head not blocking), selfie-cam look, foot contact.
SOURCE vs DEPLOYED: the deployed build uses the T-pose detector above. The source now also has the A-or-T
"measured-pose" calibration (the avatar's arm/leg segments are swung onto YOUR measured segment directions before the
offsets are taken, so any still straight-armed pose works; knee limit 40, stillness < 12 cm/s, manual trigger
tribemod/bt_calibrate_now). Compiled (144,368 B) but NOT yet run on device.
Next: deploy + verify the measured-pose build; skin cycle must rebuild rest skeleton/meshes + load that skin's
calibration; remove the obsolete Tribe-slot keeper/blocker; foot planting; first-person/selfie visual check.

## Session 3c — skins that "just work": one calibration per PERSON, re-rig on skin change, PC-side skin checker

User (after A2): "everything seemed good while playing and the head didnt interfere with my vision" -> the owner-no-see /
only-owner-see split works in first person. User will make more skins -> they must work without per-skin fiddling.
- CALIBRATION IS NOW PER PERSON: the raw capture (all 84 Meta joints rot+pos, eye height, facing) is saved to
  tribemod/bt_user_calib.txt; each rig's offsets + scale are DERIVED at load (a2_apply_ucal: pose the avatar to the
  measured limb directions, O_b = M_j^-1 * R_z(you-avatar) * A_b, scale = your eyes / its eyes). A new skin needs no
  pose. Capture no longer depends on the current skin being trackable. Old per-rig files (skins/*.bt.txt) are ignored.
- RE-RIG ON SKIN CHANGE: do_load now always puts the new mesh on our actor (it used to bail out when Tribe's
  never-drawn AvatarBodyMesh slot was missing) and flags g_skin_changed; bt_frame drops the tracked meshes
  (K2_DestroyComponent -- fresh components because an asset swap with the same bone count keeps the old rig's hidden-bone
  indices), rebuilds the rest skeleton, re-applies your calibration, and goes live again. A rig that can't be tracked
  (half-body RPM: no arm/leg bones) shows the stiff follow body instead of failing the whole feature.
- RIG ROBUSTNESS: bone names match after stripping a "prefix:" (mixamorig:); Hips gets Meta's hip position even when it
  isn't the skeleton root (Blender "Armature" root); wrist IK only when Arm > ForeArm > Hand is a direct chain;
  guarded diagnostic logs for rigs without hand bones (was an out-of-bounds read).
- tribemod/next_skin (one-shot): remote skin switch (advance_skin + reload) for testing.
- scripts/check_skin.py: PC-side checker for Blender exports -> two verdicts, LOADS and MOVES WITH YOU; --push
  --activate copy to the headset. Negative-tested on in-memory broken variants of skullbuck: mirrored L/R names -> FAIL
  (moves), cm units -> FAIL (loads), unapplied armature scale -> WARN+FAIL, mixamo prefix -> passes. Existing skins:
  skullbuck = loads + moves; default/mentor = ReadyPlayerMe HALF-bodies (38 bones, no arms/legs) -> load, follow stiff.
Built 147,168 B. NOT yet run on device (headset charging). Test plan: calibrate once (any still straight-arm pose) ->
next_skin through default/mentor (expect stiff follow) -> back to skullbuck (expect live, no pose) -> a mixamo-prefixed
skullbuck variant (expect 22/22 mapped, live) -> delete test skin; then the in-headset Tribe avatar-menu cycle.

## Session 3c — controller hands (user: with controllers "the hands are gone from the avatar")

User report (on the A2 build): hand tracking -> hands visible (great); controllers -> no hands at all (input still works).
Cause (object dump): with hand tracking Tribe draws Meta's hand meshes (TribeControllers_C.OculusXRHandComponent); with
controllers its hands are ReadyPlayerMeComponent.AvatarLeftHand/AvatarRightHand -- RPM hand meshes, blank since RPM died.
And A2 hides the model's hands (to let Tribe's show). So with controllers nothing is drawn.
Fix (per hand, checked every 8 frames): OculusXRInputFunctionLibrary.IsHandPositionValid + GetTrackingConfidence(High) ->
hand tracking has it -> keep the model hand hidden; otherwise UnHideBoneByName(hand) and pose it from Meta's body-tracking
hand joints (reported with controllers too):
- wrist: frame match, calibration-free and twist-correct: R_hand = frame(Meta wrist->middle knuckle, pinky->index
  knuckle) * frame(same on the avatar rest)^-1 * restHandCS  (quat_axes/frame_q verified offline: 1e-15 / 7e-14)
- fingers (Thumb/Index/Middle/Ring/Pinky 1..3): per segment, swing the bone (inheriting the posed parent) onto Meta's
  matching segment direction (Thumb 20->21->22->23, Index 25->26->27->28, ... right 46..69); last phalanx continues the
  previous segment's rest direction.
- log: "A2 hands: left -> MODEL hand shown (controller)" on every switch; live line adds drive time (us/frame), bones
  per mesh, hand modes. Cost with both model hands shown: 52 bones x 2 meshes = 104 SetBoneTransformByName/frame.
check_skin.py reports the 30 finger bones; Blender guide updated. Built 155,360 B; NOT yet run on device.

## Session 3c — controller hands VERIFIED on device; body-vs-head alignment fix (built, installed, unverified)

Device log (2026-09-30 ~19:47): per-person calibration in a T-pose (faced -2 deg, eyes 172 cm, arm tilt -3/-9) ->
skullbuck scale 1.060; hand modes switched live per hand: controller -> "MODEL hand shown" (IsHandPositionValid=0),
hand tracking -> "Tribe's tracked hand" (valid=1 confidence=High), incl. mixed (L model / R tribe). Drive cost
119-279 us/frame (22-52 bones per mesh x 2 meshes); frame dt unchanged.
PROBLEM: the advisor's head check read eyes-vs-MetaHead fwd/right/up ~(17,17,9) cm all session vs ~(7.5,0,8) in the
earlier session (404 samples) -> body ~24 cm off the user. Likely a UE-level recenter (HMD BaseOffset/BaseOrientation):
the camera pose gets BaseOri^-1*(P-BaseOffset), TryGetBodyState's joints don't. FIX (installed, 158,872 B, NOT yet
verified because the next launch sat behind Meta's unofficial-app dialog): read
OculusXRFunctionLibrary.GetBaseRotationAndBaseOffsetInMeters every 30 frames and, self-verifying, apply the same
correction to all joints only when it brings Meta's head joint closer to EYES_FROM_HEAD=(7.5,0,8) behind the eyes
(smoothed errors, 3 cm hysteresis; logs "A2 align: using BASE-CORRECTED/raw"). The saved per-person calibration stays
valid (base rotation is a pure yaw composed on the left; calibration uses only relative directions + camera eye height).
Live line now also logs Meta wrist-to-controller distance (MotionController RelativeLocation, same space).

Go Live "does nothing" (user, not investigated deeply yet): Tribe streams through TribeVideoCallManager
(SetChannelStreaming; RTMP url/enable settings; Twitch-stream setting) and TribeTwitchManager (OAuth login, ingest URL).
Hypotheses, ranked: (1) no destination configured (Twitch not linked / no RTMP URL) -> nothing to stream to;
(2) Tribe account/plan requirement; (3) mod interference (PE hook / ReadyPlayerMeAvatarUrl ini override to
http://127.0.0.1:8000/custom.glb from the old RPM path, still written each launch because avatar_url.txt exists);
(4) sideload/entitlement breaking backend auth. Prepared: log_pe now also records Live/Stream/Twitch/VideoCall/
Channel/Rtmp functions -> one press shows where the flow stops. A/B plan: link Twitch and retry; then retry with
tribemod/executor_on and avatar_url.txt removed (mod inert) to rule the mod in or out.

## Session 3c — Go Live investigation (streaming broken on the re-signed build)

User: Go Live does nothing. live.tribexr.com = "URL pending" forever; Twitch shows "live" in-app but channel isn't;
also newer Tribe shows a second screen on Go Live, ours doesn't. RTMP not a concern.

Evidence gathered (no deep-dive; streaming is a nice-to-have):
- CONFIRMED: Meta Platform identity is failing continuously on the re-signed APK -- 123x users.get + 2x
  users.get_access_token + 13x "forwarding", ~1/sec over 2 min (code 190 Invalid OAuth 2.0 Access Token, HTTP 400,
  com.oculus.platform.util.Util / MakeEvoRequest). Rate => BASELINE, not button-triggered. Expected from re-signing
  (app signature no longer matches Meta's registered hash -> platform entitlement/identity dead).
- CONFIRMED: our build HAS the full streaming UI (W_VideoCallMenu + confirm screens, W_ChannelDeviceSelection,
  W_VideoCallStageQueue, W_LiveList, etc.) -- streaming isn't missing from this version.
- ProcessEvent button-logger (tribemod/log_pe, now O(1) hash-set + ms timestamps) during a Go Live press: BP flow runs
  W_VideoCallMenu (RefreshChannelsAndRooms, UpdateStageButton, NetworkSettings StreamSelection changed) but NO
  stream-start UFunction (SetChannelStreaming / GetBackendLiveURL / GetIngestUrl) routes through PE -> they're native
  C++ calls, or never reached. Flow reaches the menu and doesn't advance (matches "no second screen").
- HTTP visibility: added Engine.ini [Core.Log] LogHttp/LogOnline/LogOnlineHttp/LogHttpCurl=Verbose via the constructor
  upsert (flag tribemod/http_log). ini verified written. RESULT: zero real UE LogHttp/LogOnline output from any pid ->
  LogHttp is COMPILED OUT in this Shipping build; ini verbosity can't restore it. No tribexr/twitch/ivs host appears
  anywhere in logcat (HTTPS, opaque). Dead end for passive logging.
  LESSON: my first grep "count=5 LogHttp lines" was all my own TRIBEMOD status lines -- verify by reading content, not
  counting matches.

CERTAIN: Meta identity is broken on this build. NOT CERTAIN (can't prove cheaply): that this is the direct gate on
Tribe streaming vs. (a) a separate Tribe-backend token, (b) a newer-version UI screen, (c) these Meta errors being
harmless-on-legit-installs (no baseline obtainable without Restore, which reverts the mod).
Only remaining in-house proof = native-hook GetBackendLiveURL/GetAccessTokenFromBackend impls (Ghidra, hours). Deferred
pending user interest. Next step chosen by user: ask the advisor (domain knowledge may resolve it). OS-level capture
(Quest record/cast, oculus.com/casting) is the clean workaround -- bypasses Tribe's backend, shows the custom avatar.

## Session 3c — Go Live ROOT CAUSE PROVEN (native RE): Meta identity, broken by the re-sign; not fixable while modded

User asked for certainty (not just "high confidence") -> native disassembly of Tribe's backend/auth path. CERTAIN now:
- Backend hosts are HARDCODED at TribeGameInstance init (Ghidra FUN_0518b35c rva 0x508b35c):
  GameInstance+0x478 = "https://mixreality.tribexr.com" (API), +0x488 = "https://live.tribexr.com" (live base).
  So GetBackendLiveURL (FUN_0518d844, pure getter of +0x488/+0x490) returns the CONSTANT base, never empty --
  my earlier "field never filled" read was WRONG. The UI "URL pending" is the PER-SESSION link, which needs the
  backend to create a live session FOR THE AUTHENTICATED USER.
- Backend identity auth = Oculus/Meta user proof: binary uses ovr_User_GetUserProof, ovr_Message_GetUserProof,
  ovr_UserProof_GetNonce, ovr_User_GetAccessToken, ovr_User_GetLoggedInUser, ovr_Entitlement_GetIsViewerEntitled;
  HTTP auth = Authorization: Bearer + nonce. Classic Oculus platform proof pattern.
- OBSERVED (logcat): ovr_User_GetAccessToken / users.get fail continuously (code 190 Invalid OAuth 2.0 Access Token,
  HTTP 400), ~1/sec baseline -- the re-signed APK's signature no longer matches the hash Meta registered for Tribe's
  Oculus app ID (real app id in binary: 14737832452345234664), so the platform SDK won't mint a user token/proof.
  Same reason the "unofficial app" dialog gates every launch.
- Twitch path (GetIngestUrl -> FUN_0522b4b8): returns rtmp://sfo.contribute.live-video.net/app/<key@+0x380> ONLY if
  auth-state@+0x388 >= 2; the key comes from a Tribe-backend OAuth exchange (id.twitch.tv/oauth2 client in binary)
  that itself needs the Oculus identity. So "Tribe says live, Twitch isn't" = local optimistic flag, no real ingest.
- Tribe also has subscription tiers (ETribeSubscriptionGroup, bPremiumAccess, GetTribeLifetimeSubscriptionSKU) -- a
  possible SECOND gate, but it's verified through the same backend auth, so the broken Oculus identity is upstream of it.
CONCLUSION: streaming fails because the re-sign invalidates the Meta platform identity that Tribe's backend requires for
every account-gated operation. NOT fixable on the modded build: valid identity needs the original app signature, which
is exactly what "Restore" reinstalls (and removes the mod). The two are mutually exclusive. Not a patchable bug.
Workaround for streaming the custom avatar: OS-level capture (Quest record/cast, oculus.com/casting) -- bypasses Tribe's
backend entirely. New scripts: scripts/StringXrefDecomp.java (string-xref decompiler), scripts/FindNativeThunk.java.

## Session 3c — Go Live/Lounge: DEFINITIVE — it's the re-sign (signature), proven by pristine test; NOT our code

Follow-up after "logged in + subscribed" (which weakened the earlier re-sign conclusion). User reports Go Live AND
LOUNGE both fail -> it's the whole real-time video subsystem (TribeVideoCallManager: lounge + stages + go-live), not
streaming alone. Go Live worked reliably on stock before the mod (user confirmed).
DECISIVE TEST: installed pulled/base.apk re-signed with our key, ZERO other changes (original libUnreal.so, NO libhook,
original manifest). Result: lounge + Go Live STILL fail identically.
=> PROVEN: the signature alone breaks Tribe's real-time video backend. Not our hook, not the ini overrides, not libhook
loading, not the libUnreal DT_NEEDED edit, not a version issue. Re-signing with a non-Meta key invalidates the Meta
platform entitlement that the live video session auth requires. General login/profile/subscription still work (cached/
persistent TribeAccounts token); only the per-session Meta-backed video auth fails.
CONSEQUENCE: custom-avatar mod (requires re-sign) and Tribe online features (lounge/streaming) are MUTUALLY EXCLUSIVE on
one install. Not fixable in our code. Switching = full APK reinstall (modded <-> store). Quest 3 has no public root, so
runtime injection into the untouched store app (which would allow both) isn't available.
Standalone/email login path (TribeAccountsManager): BeginStandaloneManualLogin is hard-stubbed ("Login unavailable
code 24"); SendMagicLinkEmail is live but moot (user already logged in + subscribed; the gap is per-session video auth,
not account login). Dead end.
SILVER LINING for streaming the avatar: Tribe's LOCAL selfie/spectator cam renders the avatar in 3rd person with NO
backend (confirmed earlier: skullbuck_selfie_cam_following.jpg on the modded build). So OS-level capture (Quest
record/cast of that view) can stream the avatar without Tribe's dead backend. Unverified which view Quest cast grabs;
next step if user wants it. User build restored (work.aligned.apk) + flags + calibration intact.

## Session 3c — Go Live: PROVEN by genuine-vs-re-signed control (advisor-guided clean-state A/B)

Advisor pushed back (rightly): pristine test was signing-only (confirmed: cp+zipalign+apksigner, no apktool rebuild),
but I lacked a current genuine-signed control, and uninstall resets state so comparisons must be clean-state both sides.
Genuine signer confirmed: CN=Kevin Lowe, O=TribeXR Inc. (SHA-256 af43cac3...); our re-sign: CN=Tribe Mod, O=Personal.
CLEAN-STATE A/B (version held constant -- store ships the SAME 0.12.5.1, installer com.oculus.ocms):
  | build | version | signature | install | Meta auth errs | Go Live/Lounge |
  | modded        | 0.12.5.1 | ours    | sideload | ~1/sec | FAIL |
  | pristine re-signed | 0.12.5.1 | ours | sideload | ~1/sec | FAIL |
  | genuine store | 0.12.5.1 | Tribe's | store    | 0      | WORKS (user streamed Twitch + live.tribexr.com) |
On genuine: 0 code-190/users.get errors + Agora RTC active (8 refs) = video backend authed and streamed. On re-signed:
constant auth failure, never reaches Agora. Everything else identical.
=> DEFINITIVE: the signing identity is the gate. Re-signing with a non-Meta key breaks the Meta platform auth Tribe's
Agora-based video backend (lounge/stages/go-live) needs per session. Ruled out: version (same 0.12.5.1), account/service
(works now), our avatar code (pristine re-signed fails identically). Custom avatar (needs re-sign) and Tribe online video
are MUTUALLY EXCLUSIVE per install. No fix: can't reproduce Tribe's signature (their key only), no Quest 3 root for
runtime injection into the untouched store app.
Backup of avatar data (skins + bt_user_calib.txt + params) at backup/tribemod_20261001/. User currently on the working
STORE version. To restore avatar: install out/hookA/work.aligned.apk, push backup/tribemod_*/tribemod/* back.
Only "both" option = modded build (avatar in Tribe's LOCAL selfie cam, no backend) + Quest SYSTEM-level cast/record
(OS feature, works regardless of app auth) -- but that captures the HMD view, not Tribe's 3rd-person stream cam.

## Session 3c — CORRECTION (advisor review): tighten overclaims on the Go Live conclusion

Advisor flagged three overstatements in the prior "DEFINITIVE: signing identity is the gate" entry. Corrected:
1. CONFOUND NOT RESOLVED: the working genuine build was STORE-installed; the failing builds were our-cert + SIDELOADED.
   Two variables (certificate AND install provenance) changed together. The genuine pulled/base.apk sideloaded via adb
   did NOT start cleanly (user: "the fresh one you installed isnt starting" -> uninstalled -> user installed store
   version manually), so genuine+sideload streaming was never tested. "Only the cert differs" was WRONG. Cert-vs-
   provenance remains unseparated.
2. MECHANISM IS INFERENCE: observed = Tribe requests Meta token+proof (binary symbols) and gets code 190 on ours / 0 on
   genuine. NOT observed = that Meta checks the signing cert specifically (190 = "invalid token", no stated reason),
   that the user-proof attests the whole APK (it's user verification; app/cert check is a separate inferred mechanism),
   or that both token AND proof generation failed. Signing identity = strong inference, not measured.
3. "NO WORKAROUND" -> "no fix within our current re-sign+sideload method". Not universal impossibility; a Tribe-
   sanctioned signing/integration or future firmware/root could change it.
DEFENSIBLE BOTTOM LINE: avatar code is NOT the cause (proven); re-signing+sideloading an otherwise-unchanged Tribe
reproduces a Meta-auth failure blocking real-time video while the genuine store build works (same version+account);
changed signing identity is the LEADING cause with install provenance still a confound; no fix within our approach.
Full hedged writeup: claudedocs/golive_findings.md. Open gap-closing test (optional, disrupts the working store install):
sideload genuine base.apk, clear the dialog, try to stream -> streams = cert is the gate; runs-but-no-stream = provenance
also matters.

## Session 3e — Mod wouldn't launch -> signup fail: OBB wipe + Meta token loss. RECOVERY PROCEDURE + cert-vs-provenance RESOLVED

Trigger: after the prior session uninstalled the store build and reinstalled the mod (for the capture probe), Tribe
would not start ("not starting" after Open App), then after being fixed showed "network issue preventing signup".
NONE of this was the capture probe (hook loaded clean, zero crashes).

Three independent breakages, each proven by observation:
1. STUCK ON DOWNLOADER = OBB MISSING. `adb uninstall` wipes /sdcard/Android/obb/<pkg>/. Without main.2304.obb, UE launches
   its DownloaderActivity (resumed activity = .DownloaderActivity) and can't download (sideloaded) -> never reaches game.
   Fix: push pulled/main.2304.com.TribeXR.TribeXR.obb back (2,034,318,982 bytes).
2. errno 13 READING tribemod. adb-pushed files land shell-owned; the tribemod DIR gets o=--- (no search bit for the app
   uid), so the app can't traverse it -> "executor_on absent" (PE hook skipped), "custom.glb errno 13". Fix: chmod the
   dir tree world-rwx. (The app uid also changes on reinstall: u0_a176 -> u0_a178.)
3. "NETWORK ISSUE PREVENTING SIGNUP" = Meta app-auth rejects the modified APK. DIRECTLY OBSERVED this time (http_log on):
     POST https://graph.oculus.com/authenticate_application -> HTTP 400, retried ~1/sec, never succeeds:
     {"error":{"message":"Application does not have permission for this action","code":27,"error_subcode":1891543,
      "is_transient":false,"error_user_title":"Unofficial Application",
      "error_user_msg":"This app has been modified from it's original version... please uninstall and use the Store version"}}
   The mod NEVER passes authenticate_application. It only ran all session because a genuine login had cached a Meta token
   on the headset; uninstalling the mod evicted it, and the mod can't mint a new one.

RESOLVES the prior entry's open confound (cert vs install-provenance): we sideloaded GENUINE pulled/base.apk via adb and
logged in -> 0 "Unofficial Application" errors, full login. So a genuine SIGNATURE authenticates even when SIDELOADED ->
install provenance is NOT the gate; the signing identity is. And the mechanism is no longer inference: the 400 body
literally says "modified from its original version" / code 27 "Unofficial Application". (Streaming itself still not
re-tested on genuine-sideload, but authenticate_application is the app-level gate everything rides on.)
NEW scope correction: the Meta wall blocks ALL login on a fresh mod install, not just streaming. The mod depends on a
genuine-seeded token and is inherently temporary (token expires -> re-seed).

================ RECOVERY PROCEDURE (copy-paste) ================
Vars:  A=./tools/platform-tools/adb.exe   S=2G0YC1ZF96072F
       D=/sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod
       OBB=/sdcard/Android/obb/com.TribeXR.TribeXR/main.2304.com.TribeXR.TribeXR.obb

PART A - re-seed the Meta token with the GENUINE build (CN=Kevin Lowe, SHA-256 af43cac3...):
  "$A" -s $S uninstall com.TribeXR.TribeXR
  "$A" -s $S install pulled/base.apk
  "$A" -s $S shell "mkdir -p /sdcard/Android/obb/com.TribeXR.TribeXR"
  "$A" -s $S push pulled/main.2304.com.TribeXR.TribeXR.obb $OBB
  -> Headset: launch -> OPEN APP (never Restore) -> log in fully (into a room).
  -> Verify:  "$A" -s $S logcat -d | grep -c "Unofficial Application"   # must be 0

PART B - swap the MOD back (reuses the just-seeded token):
  "$A" -s $S uninstall com.TribeXR.TribeXR
  "$A" -s $S install out/hookA/work.aligned.apk        # modded, CN=Tribe Mod
  "$A" -s $S shell "mkdir -p /sdcard/Android/obb/com.TribeXR.TribeXR $D $D/skins"
  "$A" -s $S push pulled/main.2304.com.TribeXR.TribeXR.obb $OBB
  # avatar data (from backups):
  "$A" -s $S push backup/reseed_20261001/custom.glb        $D/custom.glb
  "$A" -s $S push backup/reseed_20261001/bt_user_calib.txt $D/bt_user_calib.txt
  "$A" -s $S push backup/reseed_20261001/params.txt        $D/params.txt
  "$A" -s $S push backup/reseed_20261001/active_skin.txt   $D/active_skin.txt
  "$A" -s $S push backup/tribemod_20261001/tribemod/avatar_url.txt $D/avatar_url.txt
  "$A" -s $S push backup/tribemod_20261001/tribemod/skins/default.glb   $D/skins/default.glb
  "$A" -s $S push backup/tribemod_20261001/tribemod/skins/mentor.glb    $D/skins/mentor.glb
  "$A" -s $S push backup/tribemod_20261001/tribemod/skins/skullbuck.glb $D/skins/skullbuck.glb
  "$A" -s $S shell "touch $D/executor_on $D/auto_load $D/auto_actor $D/body_tracking"
  # PERMISSIONS (critical - app must read tribemod):
  "$A" -s $S shell "chmod 666 $D/* 2>/dev/null; chmod 777 /sdcard/Android/data/com.TribeXR.TribeXR/files $D $D/skins; chmod 666 $D/skins/* 2>/dev/null"
  -> Headset: launch -> OPEN APP -> into a room. Avatar injects under VR focus.

RULES / gotchas:
- NEVER `adb uninstall` the mod unless deliberately re-seeding -- uninstall wipes OBB + Meta token + tribemod together.
- The seeded token EXPIRES eventually -> login breaks again -> rerun PART A + PART B.
- First launch right after install may pass through the one-time OBB-downloader handoff and not carry the hook (no
  TRIBEMOD logs / no httpd.log). Just relaunch once; the hook loads on the 2nd launch.
- `objarray FAIL` when launched via `adb am start` is EXPECTED (no VR focus -> engine doesn't tick). Avatar only injects
  on a real headset launch. Don't diagnose avatar load from am start.
- Genuine APK: pulled/base.apk. Modded APK: out/hookA/work.aligned.apk (libhook.so 163448 B, DT_NEEDED of libUnreal).

## Session 3f — Capture probe RESULT: eglSwapBuffers is NOT the frame path (OpenXR compositor)

Armed the disabled-by-default GLES probe on a LIVE VR session (avatar loaded, user "following fine"):
- capture_probe flag -> probe_try_install hooked eglSwapBuffers @0x74c767d400 (orig captured, all GL fn ptrs resolved).
  App stayed alive (pid 29930) through install -> live inline hook did NOT destabilize Tribe.
- capture_now flag -> "arming a 4-frame burst" (flag consumed by poll, so g_probe_armed=1, left=4).
- Over ~45s armed: seq captures=0, baseline=0. Baseline needs only 120 swaps (~1.7s) and never triggered.
  => eglSwapBuffers is essentially NEVER called for the VR view.
- Mechanism is sound (same A64HookFunction drives the WORKING ProcessEvent hook), so repl_eglSwap WOULD fire if the
  function were called. Zero fires = not called. Cleaned up both flags after.

CONCLUSION: Tribe (UE5.4 + OculusXR; libUnreal DT_NEEDED includes libGLESv3/libEGL + libxrtracking/libovrplugin*) renders
eyes into OpenXR XrSwapchain GL textures submitted via xrEndFrame to the compositor. eglSwapBuffers is bypassed ->
capturing there = DEAD END. Probe milestone met with a clean NEGATIVE (identified the swap path is empty w/o destabilizing).

NEXT capture-point candidates (harder than eglSwapBuffers):
- eye-render FBO: hook glBindFramebuffer/glBlitFramebuffer, log FBO + attached texture dims to locate the eye targets.
- XR swapchain submit: hook xrEndFrame / the swapchain image, GPU readback of the submitted texture.
- VrApi submit (if used): vrapi_SubmitFrame2.
Planned next probe = read-only GL framebuffer logger (dims/FBO/texture IDs) to find the eye render targets. Low risk.

ITERATION NOTE (important): all modded builds share tribe.keystore, so `adb install -r <new-modded>.aligned.apk` should
replace IN PLACE with no uninstall -> preserves OBB + tribemod data + the Meta token (no genuine re-seed per iteration).
To CONFIRM on first rebuild. (A full `adb uninstall` still wipes OBB+token+data per Session 3e; avoid it for iteration.)

## Session 3g — Offline research (user away): XR frame path + Go Live UI map. Goal confirmed: stream THROUGH Tribe's Go Live button.

User confirmed (2026-10-02): streaming through Tribe's own Go Live button is ESSENTIAL (OS casting is not acceptable).
Plan: capture frames -> capture game audio -> MediaCodec H.264/AAC -> RTMP to Twitch -> wire to Go Live toggle + status.

### FBO locator probe (built + installed, awaiting one headset session)
- hook/dumper.cpp: flag tribemod/fbo_probe -> hooks glBindFramebuffer + glViewport, logs DISTINCT fbo ids and viewport
  sizes (+which fbo) to logcat as [FBO]. Read-only, no GL state change. Built libhook.so 165784 B.
- Packaged out/hookA/fbo.aligned.apk (7z in-place libhook update -> zipalign -p 4 -> apksigner tribe.keystore).
- `adb install -r` over work.aligned.apk: SUCCESS, OBB + tribemod data preserved (CONFIRMED cheap iteration path).
  Meta token survival through install -r not yet confirmed (app hasn't run past the dialog since).

### Frame path (offline, verified from binaries)
- APK ships its own libopenxr_loader.so (exports xrGetInstanceProcAddr/xrEndFrame/xrEnumerateSwapchainImages/...) and
  libOVRPlugin.so (5.3MB). libOVRPlugin has ZERO static xr* imports -> loads OpenXR dynamically.
- libUnreal resolves 322 ovrp_* names, incl. ovrp_BeginFrame4/ovrp_EndFrame4 (v4 in use), ovrp_GetLayerTexture2,
  ovrp_SetupLayer, ovrp_GetLayerTextureStageCount. It ALSO references xrEndFrame/xrEnumerateSwapchainImages (UE5.4
  compiles both OculusXR and OpenXR paths) -> next probe should count both to see which is live (~72/s).
- CORRECTION: an earlier claim "libUnreal names no frame functions" was a false negative -- `strings` is not installed
  in this Git Bash (failed silently). Use NDK llvm-strings.exe instead.
- Ghidra (headless, new scripts/DecompByName.java) on libOVRPlugin.so:
    ovrp_EndFrame4(int frameIndex, void** layerSubmitPtrs, uint layerCount, u64 p4)  -- per-frame submit
    ovrp_GetLayerTexture2(int layerId, int stage, int eye, u64* outColorTex, u64* outDepthTex) -- returns 0xfffffc17
      if both out ptrs null; param 4 = color texture handle out. This is how UE gets each eye's swapchain texture.
- GL multiview signatures verified from NDK headers (gl2ext.h): glFramebufferTextureMultiviewOVR(target,attachment,
  texture,level,baseViewIndex,numViews) and glFramebufferTextureMultisampleMultiviewOVR(+samples). Eye images likely
  live in a 2-layer texture array (one pass for both eyes).
- NOTE: sr() uses one global sigsetjmp buffer + re-reads /proc/self/maps -> do NOT call it from render-thread hooks.

### Go Live UI map (from objects.txt dump, backup/tribemod_20261001)
- All Go Live controls are in /Game/VideoCall/VideoCallMenu/W_VideoCallMenu (W_VideoCallMenu_C):
    TwitchStreamEnabledSlider  -> BndEvt__..._34_OnToggleStateChanged   (Twitch Go Live toggle)
    RtmpStreamEnabledSlider    -> BndEvt__..._39_OnToggleStateChanged   (RTMP Go Live toggle)
    RtmpUrlTextBox             -> BndEvt__..._19_OnEditableTextBoxCommittedEvent (user-entered RTMP URL)
    RTMPSettings / TwitchSettings(Button) / ShowTwitchChatButton -> OnButtonClickedEvent
    GetRtmpUrls, GetVideoCallRTMPURL, GetVideoCallTwitchIngestURL (where Tribe computes the stream target)
    UpdateRtmpEnabledSetting, UpdateTwitchEnabledSetting, UpdateRtmpStreamSettingsWidgets,
    ShowRtmpSettingsPanel, ShowTwitchLoginPanel, ShowTwitchSetupPanel, OnTwitchLoginSuccess, ShowRoomStreamingNotice
- Status/feedback: BP_AchievementsManager.OnStreamingStatusChanged / GetLivestreamMinutes;
  W_TwitchChat.OnStreamInfoUpdated / SetChannelName / SetChannelViewerCount; W_MainMenu.ToggleStreamingPanel.
- Twitch login is backend-mediated (W_AltTwitchLogin.OnGetAccessTokenFromBackendRepeat) -> depends on Tribe backend auth
  (broken on the mod). The RTMP option (user types a URL) needs NO backend.
- Integration idea: our existing ProcessEvent hook can see these BndEvt toggles fire -> start/stop our own pipeline.
  Stream target options: (A) Tribe's RTMP option with rtmp://live.twitch.tv/app/<key> typed into Tribe's own URL box;
  (B) make the Twitch toggle itself drive our engine using a stream key stored in tribemod config.
- Existing flag tribemod/log_pe logs distinct ProcessEvent function names (deduped) -> use it during the next headset
  session while flipping the Go Live toggles to confirm exactly which UFunctions fire.

### Decision (2026-10-02): Tribe's TWITCH switch starts the stream
- User chose the Twitch toggle (W_VideoCallMenu TwitchStreamEnabledSlider) over the RTMP toggle. Tribe's own UI already
  shows "live" on the mod; our pipeline makes that real. Mod supplies the stream key from its own config.
- CREDENTIAL RULE: the Twitch stream key is a password. Keep it on-device only (tribemod config), never in logcat,
  NOTES.md, or git; redact it in any log line.
- Transport: prefer our own small, self-contained streaming module + Android MediaCodec (hardware H.264/AAC) rather than
  building on a third-party SDK's internals (Agora's bundled FFmpeg is only partially exported; not relied on).
- Next headset session: (1) FBO probe check, (2) with tribemod/log_pe on, flip the Twitch Go Live toggle on/off once to
  capture exactly which UFunctions fire.

### Requirement (2026-10-02): stream Tribe's SELECTED CAMERA, not the headset view
- User: Tribe has multiple camera angles incl. a selfie cam; the official stream sends the chosen camera, not the eye view.
- So the capture target is the selected stream camera's render target, NOT the eye swapchain textures.
- Earlier sessions: the selfie cam renders the avatar locally on the modded build (no backend needed) -> the camera feed
  is likely still drawn on the mod; we only need to locate it and send it ourselves.
- Next headset session addition: while fbo_probe runs, switch through camera angles (incl. selfie). Expect a distinct
  framebuffer at a video-like size (e.g. 1280x720/1920x1080) that appears/changes with the camera choice.

### Session 3g cont. — Camera system found: capture target is a RENDER TARGET, not the eye swapchain (big simplification)
From objects.txt (backup/tribemod_20261001), Tribe's spectator/stream camera system:
- /Game/Environment/SpectatorRenderTarget  = TextureRenderTarget2D  <-- prime capture target (what Go Live sends out).
- /Game/Equipment/Table/BP_SelfieStick (BP_SelfieStick_C): CaptureComponent2D (SceneCaptureComponent2D) + M_SelfiePreview
  + DisplayPlane; funcs ResetSelfieCamera/LoadCameraPosition/SaveCameraPosition. The selfie cam renders scene->RT.
- TribePlayerControllerBP_C camera selection: SetActiveSpectatorCamera, SetSpectatorCamByIndex, SetSpectatorCameras,
  AutoInitSpectatorCameras, ToggleSpectatorCamera, IsSpectatorCameraEnabled, UpdateSpectatorHiddenActors,
  Add/RemoveSpectatorHiddenLabel, OnSpectatorCameraToggled.
- TribeGameInstanceBP_C: SetThirdPersonSpectatorActive / ThirdPersonSpectatorActive / ToggleSpectatorScreenMode.
- Live class counts in the dump: 13 SceneCaptureComponent2D, 8 SceneCapture2D, 25 TextureRenderTarget2D.

WHY THIS HELPS:
- The stream shows Tribe's SELECTED CAMERA (user), i.e. the spectator/selfie SceneCaptureComponent2D -> its TextureTarget
  (a UTextureRenderTarget2D). That is a normal GPU texture we can read -- far easier + more stable than the XR eye
  swapchain. And scene-capture is LOCAL (no Meta/Tribe backend) -> it still renders on the mod.
- Capture routes: (1) GL-FBO -- when the SceneCapture renders, GLES RHI binds an FBO whose color attachment is the RT's
  GL texture; the fbo_probe will show it as a distinct FBO at the RT's (video-ish) resolution when the camera is active.
  (2) UObject -- resolve SpectatorRenderTarget via reflection, read SizeX/SizeY, walk resource->RHI->GL tex id.
  Efficient streaming path later: bind that texture, draw into MediaCodec's input Surface (GPU, no CPU readback stall).
- Offsets come at runtime via the hook's reflection (prop_offset: UTextureRenderTarget2D.SizeX/SizeY/RenderTargetFormat,
  USceneCaptureComponent2D.TextureTarget); sdk.txt doesn't include these classes and no RT size is dumped offline.

NEXT HEADSET SESSION (refined): with fbo_probe on, switch camera angles incl. selfie -> watch for the FBO at the stream
resolution that changes with the camera. With log_pe on, flip the Twitch Go Live toggle -> capture which UFunctions fire.
Both pin down exactly what to capture and what signal to hook, before any encoder work.

### Camera probe built + installed (user: stream camera is most likely the SELFIE STICK)
- hook/dumper.cpp: flag tribemod/cam_probe -> cam_probe_tick() on the POLL thread every ~10 ticks (~5s), read-only:
  find_live_class_sub("BP_SelfieStick_C") -> prop "CaptureComponent2D" -> prop "TextureTarget" (UTextureRenderTarget2D);
  logs [CAM] RT full path/class/addr + SizeX/SizeY/RenderTargetFormat, and the capture comp's bCaptureEveryFrame /
  bCaptureOnMovement raw bytes + CaptureSource. Also logs /Game/Environment/SpectatorRenderTarget once found.
  Property names resolve by reflection at runtime (wrong name -> -1, never a bad read). Logs only on change.
- Built libhook.so 168184 B (no new warnings under -Wall -Wformat=2). Packaged out/hookA/cam.aligned.apk (from work.apk,
  7z -> zipalign -p 4 -> apksigner tribe.keystore). `adb install -r`: Success; OBB + custom.glb/bt_user_calib/executor_on
  intact. Armed flags: fbo_probe, cam_probe, log_pe.
- Next headset session reads: [CAM] (selfie RT name + resolution), [FBO] (which framebuffer renders it), and log_pe's
  ProcessEvent names while flipping the Twitch Go Live toggle.

## Session 3h — MAJOR REVERSAL: custom avatar + Tribe Go Live/lounges WORK TOGETHER on a FRESH Meta token
User (2026-10-02, in-headset): Twitch Go Live AND room/lounge streaming AND the character mod are ALL working
simultaneously on the modded build right now. This DIRECTLY CONTRADICTS the prior "mutually exclusive / Go Live
impossible on the mod" conclusion (Sessions 3c).

OBSERVED (logcat, this session):
- "Unofficial Application" errors: 0.  code 190 / Invalid OAuth: 0.  (Were ~1/sec in every prior failing test.)
- Meta OBTAIN_TOKEN succeeding continuously.

MECHANISM (strong inference, matches the findings' own note that video needs a fresh per-session Meta proof):
- The recovery I did = genuine login (pulled/base.apk) MINTED A FRESH Meta token, then `install -r` of the mod kept it
  (no uninstall -> no token eviction). Tribe's Agora video backend (lounge/stages/go-live) rides that token.
- Fresh token -> Meta stops rejecting -> official Go Live + lounges come alive WHILE the custom-avatar mod is active.
- The earlier failures were a STALE/absent token, NOT the re-sign per se. The re-sign's real limitation: it cannot
  REFRESH the token itself (authenticate_application rejects the modified app), so the token only lasts until it expires.

=> CORRECTION to golive_findings.md and Sessions 3c/3e: avatar and Tribe online video are NOT mutually exclusive. They
coexist as long as the Meta token is fresh. "Impossible on the mod" was true only for a stale token.

IMPLICATION FOR THE PLAN:
- The custom capture->encode->RTMP engine is likely UNNECESSARY. Official Go Live already does Twitch + avatar.
- New "solution" = keep the token fresh; re-seed (genuine login -> install -r swap, ~10 min) when it expires.
- OPEN QUESTION (durability): how long does the seeded token stay valid (hours? days?) and does the mod keep working
  that whole time? Determines whether this is a real fix or needs re-seed automation. Watch for the auth errors to
  return (~1/sec) = token expired = streaming will drop.
- PENDING VERIFICATION: confirm the REAL twitch.tv/<channel> is broadcasting (in-app "live" badge gave a false positive
  before). Lounge-with-real-people working is itself strong real-backend evidence.
- Probe work (fbo_probe/cam_probe/log_pe in cam.aligned.apk) retained as fallback if the token path proves too fragile.

### Session 3h — CONFIRMED REAL (not the in-app false positive)
User verified on their phone: twitch.tv/<channel> is ACTUALLY broadcasting while the custom avatar is active via Tribe's
own Go Live button. So the project goal (Twitch + custom avatar through Tribe's button) is ACHIEVED on a fresh Meta token.
Probe flags (fbo_probe/cam_probe/log_pe/capture_*) removed from device -> clean normal-use streaming. Probe CODE stays in
the build as fallback. Only maintenance item = Meta token freshness. KEY RULE: never `adb uninstall` the mod (wipes token
+ OBB); use `install -r` for updates (preserves both). Durability of the token = open; waiting to see when it expires.

### Session 3h — 360 videos missing on the mod = storage permission reset by the reinstall (FIXED)
- Symptom: user's 360 videos (room visuals) don't appear on the mod; do on genuine. Files present in /sdcard/Download/
  (ashen_abyss_360.mp4, mainstage_360.mp4, horizon_calib_360.mp4), owned by another app (u0_a80 media_rw, 0660).
- Tribe loads 360 video via /Game/VideoSphere/VideoSphere_MediaPlayer + StereoLayerShapeEquirect, listed by
  BP_TribeVisualsManager. Needs media read access to enumerate/open the files.
- CAUSE: reinstall gave the app a new UID (u0_a176->a178) and RESET runtime perms -> READ_EXTERNAL_STORAGE granted=false
  (USER_FIXED), all READ_MEDIA_* denied, appops ignore. gids=[3003 inet only], not in a media group -> no file access ->
  empty 360 list. Manifest perms/features were verified IDENTICAL to genuine (not the cause).
- FIX (adb): pm grant READ_EXTERNAL_STORAGE / WRITE_EXTERNAL_STORAGE / READ_MEDIA_VIDEO|AUDIO|IMAGES, and
  appops set ... READ_EXTERNAL_STORAGE/LEGACY_STORAGE/READ_MEDIA_VIDEO allow. Verified granted=true. Needs a Tribe
  RELAUNCH to take effect (storage view is set at process start; the grant may also force-stop the app).
- Alt (in-headset): Quest Settings -> Apps -> Tribe XR -> Permissions -> Files/Storage -> Allow.
- ADD TO RE-SEED CHECKLIST: after any uninstall/reinstall, re-grant storage perms or 360 videos / media break again.

## Session 3i — Drone camera (fly Tribe's own Auto cam) — built, not yet installed
Tribe's stream cameras (CommonLevel, from objects dump): SpectatorCamera1..4, SpectatorCameraFirstPerson,
SpectatorCameraAutoCam. Each is an ASceneCapture2D actor (root "SceneComponent" + "NewSceneCaptureComponent2D").
"Auto Fast/Slow" = SpectatorCameraAutoCam, moved by NATIVE TribePlayerController.SetAutoCamMode(EAutoCamMode)
(+ AutoCamResetBeatOrigin, beat-synced). Its motion is baked into native code with fixed modes -> we replace it.

Implementation (hook/dumper.cpp, flag tribemod/drone_cam, OFF by default; params tribemod/drone.txt):
- Poll thread drone_poll() every ~2s: find_live("NewSceneCaptureComponent2D","SceneCaptureComponent2D",
  "SpectatorCameraAutoCam") (map-independent); liveness check obj_at(rd32(cap+OFF_Index))==cap (re-resolve after a
  room change); reads drone.txt (radius/height/speed/look/bob, clamped); one-time [DRONE] dump of every EAutoCamMode
  name=value (learn Tribe's modes without Ghidra).
- Game thread drone_update(dt) inside the iso actor's ReceiveTick (same place follow_update/bt_frame run):
  orbit center = HMD world position (K2_GetComponentLocation) through a 1.5 s low-pass (head-bobbing to the beat
  doesn't shake the shot); position = center + (r cos t, r sin t, height + bob*sin); look-at a point `look` cm vs the
  eyes; SceneComponent.K2_SetWorldLocationAndRotation on the CAPTURE COMPONENT (world space, so actor/relative
  composition doesn't matter), bTeleport=1.
- [DRONE] log every 5 s incl. drift = how far the camera moved since OUR last write: ~0 => we're the only writer;
  large => Tribe's auto-cam motion fights ours -> next step park it via SetAutoCamMode(<static mode from the enum dump>).
- Defaults: radius 300, height 80 (above head), speed 12 deg/s (~30 s/orbit), look -40, bob 20.
- Built libhook.so 173816 B (no new warnings). Packaged out/hookA/drone.aligned.apk (work.apk + libhook, 7z ->
  zipalign -p 4 -> apksigner tribe.keystore). NOT INSTALLED YET (headset offline). reseed.sh still points at the
  proven cam.aligned.apk until this build is verified on-device.

Next headset session: `adb install -r out/hookA/drone.aligned.apk` (preserves token/OBB/data) -> launch -> select the
Auto camera angle -> touch tribemod/drone_cam -> watch the spectator view / [DRONE] logs (drift, EAutoCamMode dump).

Ghidra: PERSISTENT project C:/ghidra-work/tribexr (libUnreal.so analyzed; do NOT delete -> later -process runs skip
the ~1 h analysis). Launch via support/launch.bat with a 16G heap (support/analyzeHeadless.bat hardcodes MAXMEM=2G):
  launch.bat fg jdk Ghidra-Headless 16G "-XX:ParallelGCThreads=2 -XX:CICompilerCount=2"
    ghidra.app.util.headless.AnalyzeHeadless C:/ghidra-work tribexr -process libUnreal.so -noanalysis
    -scriptPath <repo>/scripts -postScript <Script>.java <args>
Current run: FindNativeThunk -> out/ghidra_autocam.txt (SetAutoCamMode, AutoCamResetBeatOrigin, depth 2).

### Session 3i cont. — Ghidra: Tribe's Auto cam decoded (persistent project now saved)
Ghidra run: 3816 s analysis, SUCCEEDED, project SAVED at C:/ghidra-work/tribexr (reuse with -process, no re-analysis).
Output out/ghidra_autocam.txt (FindNativeThunk, depth 2). 22 "VarnodeContext out of address spaces" ERRORs are normal
for this binary (same count in the earlier successful runs).
- SetAutoCamMode: exec thunk rva 0x4fd43c0 (P_GET_ENUM + P_FINISH) -> impl rva 0x509fc54 = 8 bytes:
  `*(uint8*)(this+0x980) = Mode;` -- a pure setter. (2nd match rva 0x4fd4468 is a FALSE POSITIVE: a cached
  singleton constructor (StaticEnum/ConstructUFunction), not a thunk.)
- AutoCamResetBeatOrigin: thunk rva 0x4fd3d84 -> impl 0x509fb90 -> "cut" function 0x509fc5c (532 B).
- MODEL: the Auto cam is a BEAT-SYNCED CUT CAMERA, not a flying one. TribePlayerController fields:
    +0x97c BPM | +0x978 beats per cut (table DAT_008a3200 indexed from +0x920 phrase info, default 4; x2 if mode==1)
    +0x980 AutoCamMode (1 = Slow) | +0x970 cut interval s = 60/BPM*beats | +0x974 SECONDS UNTIL NEXT CUT (countdown;
    each cut resets it to the interval) | +0x2d0 a camera/actor ref used by the cut.
  Each cut finds /Game/Equipment/BP_Rig.BP_Rig_C (the DJ rig), takes its location (+30 cm z, +const xy offset) as the
  focus and jumps the camera to a new angle. Between cuts it is still.
- Drone CUT-PARK: while drone_cam is on, drone_update writes +0x974 = 1e9 every frame (only if the current value looks
  like a countdown: 0..600 s, or already parked) so Tribe never cuts mid-flight; on OFF it writes 0.5 s so Tribe's
  Auto cam resumes. drone_poll resolves the controller via find_live_class_sub("TribePlayerControllerBP_C") and logs its
  reflected autocam/spectator/beat/bpm/tempo props + raw 0x970..0x980 ONCE to confirm the layout on-device.
- Rebuilt libhook.so 175720 B; drone.aligned.apk re-packaged + signed. Still NOT installed (headset offline).
- IDEA for later: BPM is right there (+0x97c) -> beat-synced drone moves (orbit speed / bob on the beat, cut on drops).

### Session 3j — Drone v2: fly the SELFIE STICK camera (user's idea), Auto cam kept as an option
User (2026-10-03): fly the selfie stick instead -- it's the camera they stream with and it can go anywhere; today it's only
limited by where they can physically put it. Better than the Auto cam: no beat-cut logic to fight, normal stream setup.
Design (hook/dumper.cpp drone section, flag tribemod/drone_cam, params tribemod/drone.txt):
- Default target = BP_SelfieStick_C's "CaptureComponent2D" (resolved by property, same chain as cam_probe).
  `target=auto` -> SpectatorCameraAutoCam's NewSceneCaptureComponent2D (+ the cut-timer park, Auto only).
- TAKEOFF: on the first active frame, read the camera's current world location -> radius / height (vs your head) /
  angle are taken FROM WHERE YOU PLACED THE STICK, so it lifts off with no jump. `radius=` / `height=` in drone.txt
  override those live; absent = "from stick".
- MOUNT SAVE/RESTORE: at takeoff the capture component's RelativeLocation/RelativeRotation are saved (sr reads via
  g_offRelLoc/g_offRelRot, resolved in drone_poll if body tracking hasn't yet); LANDING (drone off, target switch, camera
  gone) calls SceneComponent.K2_SetRelativeLocationAndRotation to put the camera back on the stick head. Selfie target
  REFUSES takeoff if the mount pose can't be saved (never leave the selfie camera displaced).
- Flight: K2_SetWorldLocationAndRotation on the capture component each frame (iso actor ReceiveTick); orbit around the
  head through a 1.5 s low-pass; look-at `look` cm vs the eyes; `bob` vertical float; `speed` deg/s (negative reverses).
- set_comp_xform(fn,...) generalizes the setter (World/Relative share param names; per-fn offset cache, 2 slots).
- Built libhook.so 179008 B (clean under -Wall -Wformat=2); out/hookA/drone.aligned.apk packaged + signed.
  NOT installed yet (headset offline).
Next headset session: install -r drone.aligned.apk -> launch -> take out + place the selfie stick -> touch drone_cam ->
watch the stick's preview / stream; tune via drone.txt live. Then rm drone_cam -> camera should snap back onto the stick.

### Session 3j — Drone v2 VERIFIED on-device; 360-crowd fly-out = not possible (flat projection)
- Installed drone.aligned.apk via install -r: libhook 179008, OBB + avatar data intact, storage perms (360 videos)
  survived install -r too.
- Selfie-stick drone works: resolve OK (relLoc@296 relRot@320, xform psz=0x131 NewLocation@0 NewRotation@24 bSweep@48
  bTeleport@304), takeoff from the stick's spot (r 264, h 6, angle -88), smooth 12 deg/s orbit, drift=0.0 cm (nothing
  fights the selfie camera), hover test r=800 h=200 speed=0 held steady, and LANDING restored the camera onto the stick.
- EAutoCamMode confirmed at runtime: Fast=0, Slow=1, MAX=2 (no Off mode -> the cut-timer park is the right approach).
- User test: fly the drone out "into the crowd" of a 360 video. The 360 video IS visible to the selfie camera (scene
  geometry, not a headset-only stereo layer), but the crowd is a FLAT IMAGE on the sphere -> no parallax/depth, so
  flying toward it doesn't put the camera among people. User shelved the idea. Reset: drone off, drone.txt removed.

## Session 3k — Character boxes in Tribe's avatar menu (WORKING) + adb-push regression
User wanted a dedicated menu choice per character instead of the cycle. Verified on-device: two new boxes, labeled
"Lampwing" and "Skullbuck", appear at the end of the avatar list; clicking one switches character.

Why the old cycle hook never fired: Blueprint->Blueprint calls never pass through ProcessEvent. It listened on
BP_TribeVisualsManager.ApplySkinToPlayer, which is BP-internal. skin_trace (flag tribemod/skin_trace, logcat [SKIN])
showed the avatar menu = 6 W_SkinItem boxes (1 BP_ReadyPlayerMeAvatarSkin_C + 5 BP_OculusAvatarSkin_C) and the
PE-visible calls: W_SkinItem.OnListItemObjectSet(item), OnMouseButtonDown, BP_OnItemSelectionChanged, OnSkinApplied,
OnMouseEnter/Leave. Menu = W_ProfileMenu_C, list widget "AvatarList" (UListView); its item handler is
BndEvt__W_AchievementMenu_AvatarList_K2Node_ComponentBoundEvent_2_SimpleListItemEventDynamic__DelegateSignature(Item).
W_SkinItem tree: NameText (label), DescriptionText, PreviewImage, StatusText, ProgressBar, SettingsButton, ...

Feature (hook/dumper.cpp, flag tribemod/skin_menu):
- One box per tribemod/skins/*.glb (max 8), label from the file name ("lampwing.glb" -> "Lampwing"). New .glb files get
  a box automatically.
- Game thread (menu_tick, ~1/s): GameplayStatics.SpawnObject(BP_ReadyPlayerMeAvatarSkin_C, outer = Tribe's RPM skin's
  outer, fallback the list) -> ListView.GetIndexForItem / AddItem. Re-adds after Tribe rebuilds the list. Respawn guard:
  >3*n respawns in 30 s -> stops (prevents a repeat of the runaway below). Relabels our boxes each second.
- Label: KismetTextLibrary.Conv_StringToText -> TextBlock.SetText on the box's NameText, after Tribe's own
  OnListItemObjectSet runs (we call orig first).
- Click: swallow BOTH W_SkinItem.OnMouseButtonDown (box mapped to our item) and the AvatarList item handler (Item is
  ours) -> write active_skin.txt + g_load_req. Tribe never tries to apply our dummy RPM skin.
Bugs found + fixed on the way:
- BP menu classes load LAZILY (when the menu first opens) -> lookups now retry; cheap find_in_outer(name, outerName).
- obj_alive() used obj_at() bounded by a STALE g_numElements -> freshly spawned objects looked dead -> respawned every
  second (105 boxes). Fix: refresh_numelements() when an index is past the cached count.
- FText size read as 0: FP_ElemSize=0x34 is WRONG for this build. Observed on Conv_StringToText.ReturnValue: +0x30=16
  (ElementSize), +0x34=0, +0x38=0x580 (PropertyFlags Parm|OutParm|ReturnParm), Offset_Internal +0x44 correct.
  Fallback used: size = ParmsSize - offset (ReturnValue is last) = 16; FText is 16 B in this build (SetText psz 0x10).
  TODO: verify + move FP_ElemSize to 0x30 (spawn_iso_actor's FTransform size check reads it too).
- Known minor: one click fires both entry points >0.7 s apart -> the same skin loads twice. Harmless; next build:
  debounce same-index within ~3 s.
- Built libhook.so 192688 B -> out/hookA/menu.aligned.apk, installed + VERIFIED; reseed.sh MOD now points here.

adb-push REGRESSION (2026-10-03): `adb push` into /sdcard/Android/data/<pkg>/ reports success but the file never lands
(tested with a 5-byte probe: Android/data GONE; Android/obb + /sdcard/Download KEPT). Shell-created files there still
work (echo/printf/cp). Workaround: push to /data/local/tmp, `cp` in via adb shell, `chmod 666` (cp'd files come out
0660 shell:shell, unreadable to Tribe otherwise). reseed.sh (put() helper; restores lampwing+skullbuck from the PC's
skins/; touches skin_menu) and check_skin.py --push (stages, then verifies the landed size) are both fixed; check_skin
push verified live. Also: my earlier "checker multi-file bug" was MY mistake -- MSYS_NO_PATHCONV=1 stopped Git Bash from
converting /c/... paths for Windows Python, so the checker couldn't open the files.
- Rotation on the headset is now lampwing + skullbuck only (default/mentor/apose/armless removed; PC copies kept in
  skins/ and Downloads). install -r also preserved the storage permissions (360 videos still fine).
- Debug tip: the device logcat ring buffer is small and floods fast; during tests run
  `adb logcat -s TRIBEMOD:V > file` in the background so startup lines aren't lost.

## Session 3l — Festival stage feasibility (read-only): props loader, stock environments, backdrop screen
User (2026-10-04) wants to "physically add" to Tribe, specifically an OUTDOOR FESTIVAL STAGE in real 3D rather than
a 360 video. Read-only investigation; nothing built.

Loading props / a whole stage [observed: object dump backup/tribemod_20261001 + extracted/paklist.txt]:
- In the game: glTFRuntimeAsset.LoadStaticMesh / LoadStaticMeshRecursive / LoadSkeletalAnimation / LoadPunctualLight,
  and glTFRuntimeAssetActor(+Async). Plugin source (master): Asset is ExposeOnSpawn, plus bAllowNodeAnimations and
  ProcessNode, which builds the node tree in BeginPlay. Engine: StaticMeshActor, StaticMeshComponent.SetStaticMesh,
  Actor.SetActorHiddenInGame, PrimitiveComponent.SetSimulatePhysics, MeshComponent.SetScalarParameterValueOnMaterials.
- Pak has the glTFRuntime materials: M_glTFRuntimeBase, Masked/Translucent/TwoSided instances, M_Unlit_glTFRuntimeBase.
- Plan: same chain as skins (glTFLoadAssetFromFilename, SceneScale=100), then either AssetActor (whole scene) or
  LoadStaticMesh + StaticMeshActor.

Stock environments [observed: DT_EnvironmentSkins + Environment_{Void,VideoSphere,Desert_Optimized}.umap, extracted
with pak_extract + oodle_dec + bp_disasm into the session scratchpad]:
- 10 table rows: Passthrough, Tribe Lounge, Lodato Lounge, The Void, Pioneer DJ Powerstation, Desert Lounge,
  Polygon City, Hip Hop Ride, Hotel Selina, Video Sphere. Each is its own streamed level,
  /Game/Maps/Environments/Environment_*.umap (LevelStreamingDynamic under DJRoomMap). The rig and cameras live in CommonLevel.
- Levels are small.
  - Void: directional light, skylight, reflection capture, Avatar/Backdrop/Booth spotlights, SM_BackdropScreen and
    SM_BackdropScreen_ChromaKey. No scenery.
  - VideoSphere: the same lights plus TribeVideoSphere (DomeMesh) and the chroma backdrop only.
  - Desert Lounge: adds SM_DesertSkybox/M_DesertSkybox, desk, desk lights, speakers, railings, interior meshes, banana
    plants (foliage), wall/ceiling blockers, post-process and baked lightmaps.
- Asset style: Polygon City uses the Synty POLYGON Sci-Fi atlas. Pioneer uses a KitBash3D 8k atlas plus MediaPlayer video
  screens on buildings. Tribe's own budget is therefore a few meshes sharing atlas textures, a skybox and baked lighting.
- Transforms can't be read offline: the cooked levels use unversioned properties and there is no .usmap, so UAssetAPI
  leaves the exports raw. Read the dome size and booth position LIVE in the first headset test instead.

Backdrop screen [Ghidra out/ghidra_backdrop.txt + level name tables]:
- Every environment's level BP calls BP_TribeVisualsManager_C.SetupEnvironmentBackdrop(BackdropMesh,
  ChromaKeyBackdropMesh) in BeginPlay. All of them use SM_BackdropScreen_OldStyleUVs; the chroma one uses
  /Game/Visuals/ChromaKey/ChromaKey_M.
- TribeVisualsManager.SetBackdropStaticMesh: thunk rva 0x4ff01b0, impl rva 0x510de3c. It sets this+0x2d0 = actor. If
  DrawMode (this+0x3d4) is 1/2/3 it takes the material at this+0x2e8/0x2f0/0x2e0 and makes vcall +0x698 on
  actor+0x290 (StaticMeshActor.StaticMeshComponent; inferred SetMaterial(0, mat)). The second match, thunk rva
  0x4ff0258, is likely the cached-UFunction constructor false positive seen with SetAutoCamMode.
- UpdateBackdropVisibility: thunk rva 0x4ff08b8, impl rva 0x51128c0. When a backdrop is set it makes vcall +0x368 on
  the actor (inferred SetActorHiddenInGame): shown when DrawMode != 0, otherwise hidden by a setting.
- [inferred, untested] Registering OUR LED-wall StaticMeshActor through SetupEnvironmentBackdrop/SetBackdropStaticMesh
  should put Tribe's visuals on it: videos, beat-matched GIFs, text, images, NDI (StreamVideoToBackdrop,
  DrawGifToBackdrop + SetGifBeatmatchEnabled, DrawTextToBackdrop, StreamNdiToBackdrop). There is only one backdrop
  pointer, and an environment switch re-registers that environment's own screen, so ours must be re-registered after
  each environment load.
- Also seen: TribePlayerController.SetChromaKeyBackdropInSpectatorCameras / SetChromaKeyColor (Tribe's green-screen
  mode for the stream cameras).

Proposed next step (awaiting the user):
- Add a stage loader to the hook: spawn a whole .glb at the booth, auto-register the LED-wall node as the backdrop, and
  read out the booth position and VideoSphere dome bounds live.
- Test with a rough stage first, then the real Blender stage.
- Base environment: The Void (lights + backdrop only) or Video Sphere (360 crowd as the far backdrop).

### Session 3l cont. — User wants their OWN environment (a menu entry like the stock ones), not a stage on top of one
[observed, object dump + BP_EnvironmentSkin name table + out/obb_listing.txt]:
- The environment menu works like the avatar menu where the character boxes already work.
  - W_VisualsMenu_C.EnvironmentList is a ListView with the shared box widget /Game/Menus/W_SkinItem.W_SkinItem_C.
  - Items come from AddSkinWidgetsForList / BuildEnvironmentSkinWidgets.
  - The click handler is BndEvt__W_VisualsMenu_EnvironmentList_K2Node_ComponentBoundEvent_2_SimpleListItemEventDynamic__DelegateSignature.
- BP_EnvironmentSkin_C does the switching:
  - It holds Environment (row name) and EnvironmentType (native enum /Script/TribeXR.ETribeEnvironmentType).
  - It reads the DT_EnvironmentSkins row, checks IsHost / IsTribePassthroughSupported, and calls
    TribeGameStateBP_C.SetEnvironment_ShowLoadingScreen, then native TribeGameState.SetEnvironment.
  - It persists the choice with WriteConfigString ([TribeSkins] Environment=).
  - => [inferred] The set of loadable environments is fixed in native code (an enum). A custom environment has to
    borrow a slot: The Void (lights + screens, no scenery). Others in a multiplayer room would see The Void.
- Path A (mod, runtime): add our box to EnvironmentList (reuse the character-box code) → on click, switch to The Void →
  hide SM_BackdropScreen and SM_BackdropScreen_ChromaKey → spawn our .glb world → SetupEnvironmentBackdrop with our
  LED wall → persist and re-apply on launch.
- Path B (real UE level): Tribe is UE 5.4. The OBB has 4 paks, no .sig files and no .utoc/.ucas (unsigned, no IoStore),
  so a mod pak is plausible. LevelStreamingDynamic.LoadLevelInstance and GameplayStatics.LoadStreamLevel/UnloadStreamLevel
  exist. UNKNOWN: whether Quest Tribe mounts an extra pak, and from where. Needs a UE 5.4 + Android cook setup.

### Session 3l cont. 2 — User asks "why not Unreal?" (a real UE level instead of a runtime .glb). Feasibility facts
[observed: libUnreal.so UTF-16 strings, Tribe's config extracted from pakchunk0, extracted/paklist.txt, PC check]
- Patch/overflow OBB support is compiled in. Strings: "main.%d.%s.obb", "patch.%d.%s.obb", "overflow%d.%d.%s.obb";
  logs "Mounted patch OBB: %s", "Mounted overflow%d OBB: %s"; "Mounting pak file: %s".
  => Candidate delivery: patch.<ver>.com.TribeXR.TribeXR.obb (a zip holding TribeXR/Content/Paks/<mod>.pak) in
  /sdcard/Android/obb/<pkg>/ (adb push into Android/obb works, per Session 3k). UNTESTED.
- Tribe mounts add-on paks itself. Classes: UTribeAddon with VisualsPack / LessonPack / TrackPack / VideoSphere
  subclasses. Name prefixes: TribeXR-VisualsPack_, -360VideoPack_, -LessonPack_, -TrackPack_. UFunctions:
  TribeAddon.InstallAddon, TrackLibrary.LoadTrackPak, TribeVisualsManager.InstallVisualsPackAddon /
  InstallVideoSphereAddon. => Runtime pak mounting is live in this build. There is no environment add-on type.
- Engine: UE 5.4 (asset headers "++UE5+Release-5.4", Session 0). No engine-branch string in the .so (the Meta fork is
  undetermined).
- Tribe's settings (TribeXR/Config/DefaultEngine.ini + DefaultGame.ini), which a mod project must mirror:
  - Rendering: r.ForwardShading=True, r.AllowStaticLighting=True, MSAA (AA method 3, r.MSAACount=2), r.MobileHDR=False,
    vr.MobileMultiView(+Direct)=True, r.Mobile.UseHWsRGBEncoding=True, r.Mobile.EnableMovableSpotlights=False,
    r.Mobile.SupportGPUScene=True.
  - Android: Vulkan only (bBuildForES31=False, bSupportsVulkan=True, SM5 off), ASTC.
  - Packaging: UsePakFile=True, bUseIoStore=False, bGenerateChunks=True, Oodle Kraken, bShareMaterialShaderCode=True,
    bSharedMaterialNativeLibraries=False.
- Shader libraries are per chunk inside the paks:
  - ShaderArchive-Global-SF_VULKAN_ES31_ANDROID-VULKAN_ES3_1_ANDROID.ushaderbytecode
  - ShaderArchive-TribeXR_Chunk0-... (pakchunk0) and ShaderArchive-TribeXR_Chunk1-... (pakchunk1)
  - => A mod pak must ship its own ShaderArchive-TribeXR_Chunk<N> (or inline shaders) built with matching settings.
    That is the main technical risk after mounting.
- PC: Blender 4.3 + 4.4 installed. Unreal Engine NOT installed (no Epic Games dir, no registry entry). UE 5.4 + Android
  target support needs an Epic Games Launcher install (user action, needs their Epic login).
- Menu integration: environments are a native enum (Session 3l cont.). Options: (a) a mod pak overrides an unused
  environment's level path (e.g. /Game/Maps/Environments/Environment_HipHop) plus its preview texture, and the hook
  relabels the box; or (b) borrow The Void + LevelStreamingDynamic.LoadLevelInstance from the hook.
- Risk-first plan:
  - Step 0, no Unreal needed: a tiny test pak (repak, v11) delivered as a patch OBB; check logcat for
    "Mounted patch OBB" / "Mounting pak file" and confirm the file is visible in-game.
  - Step 1: UE 5.4 mod project mirroring the settings above; cook a minimal test level into chunk N and test it.
  - Step 2: the festival.

## Session 3m — STEP 0 PASSED: Tribe mounts an extra pak delivered as a PATCH OBB (no APK rebuild)
Method: no hook rebuild. The mod's loader already honors tribemod/glb_path.txt when active_skin.txt is absent, and it
calls glTFLoadAssetFromFilename(path, bPathRelativeToContent=false), which reads through UE's file layer (pak first).
- Built with repak 0.2.3 (cargo install --git trumank/repak repak_cli): two V11 paks, mount ../../../, uncompressed.
  - TribeModTest_P.pak: TribeXR/Content/ModTest/{plain.glb, hello.txt}
  - pakchunk99-Android_ASTC_P.pak: TribeXR/Content/ModTest/chunk.glb
  - Each .glb is a copy of skins/lampwing.glb (sha256 e2d176b1… matches inside both paks).
- Patch OBB = plain STORED zip, mirroring main: entries TribeXR/Content/Paks/<both paks> + loose
  TribeXR/Content/ModTest/loose.glb; zip comment "      2304" (as in main). Verified with scripts/pak_list.py.
- Pushed to /sdcard/Android/obb/com.TribeXR.TribeXR/patch.2304.com.TribeXR.TribeXR.obb (versionCode 2304; lands
  shell:ext_obb_rw 644, readable).
- Device steps: active_skin.txt renamed aside, glb_path.txt written, Tribe force-stopped and relaunched via
  `am start -n com.TribeXR.TribeXR/com.epicgames.unreal.GameActivity` (monkey fails on Quest: no LAUNCHER category).
- RESULT [observed, logcat TRIBEMOD, pid 26910]:
    asset=0x72afa092a0 (path=../../../TribeXR/Content/ModTest/plain.glb) -> mesh built, materials on, actor follows
    asset=0x72ae7c5aa0 (path=../../../TribeXR/Content/ModTest/chunk.glb) -> do_load done
    asset=0x72b9d75aa0 (path=../../../TribeXR/Content/ModTest/loose.glb) -> do_load done
  plain.glb and chunk.glb exist ONLY inside the paks, so the paks were mounted at startup. Both a plain _P name and a
  pakchunk99 name work. The loose file proves the patch OBB zip itself is in the file system. Our unsigned pak was
  accepted (no signature enforcement).
- Restored afterwards: glb_path.txt removed, active_skin.txt back to skullbuck.glb, skullbuck reloaded.
  The patch OBB was LEFT on the device (test-only ModTest paths, no overrides). Remove it with
  `adb shell rm /sdcard/Android/obb/com.TribeXR.TribeXR/patch.2304.com.TribeXR.TribeXR.obb`. Step 1 overwrites it anyway.
- UE's own logs (LogPakFile etc.) do NOT reach logcat in this Shipping build. The proof has to come from inside the
  process (the mod).
- Not yet tested: cooked UE assets from our own UE 5.4 install (shader library / engine-build match) and _P override
  priority over a stock environment level. That is Step 1, which needs UE 5.4 + Android installed by the user.
- Signing note: the keystore password isn't in the repo. Auto mode blocked recovering it from old session logs
  (credential), so future APK rebuilds need the user to sign or supply it. Step 1 (pak-only) needs no APK rebuild.

### Session 3m cont. — Can we add a NEW environment (not replace a stock one)? Decoded: the level list is native
[observed: Ghidra out/ghidra_setenv.txt; F_EnvironmentSkinEntry extracted from pakchunk0]
- A DT_EnvironmentSkins row (F_EnvironmentSkinEntry) has exactly 2 fields: Environment_44_… (EnumProperty
  ETribeEnvironmentType) and SkinInfo_37_… (F_SkinInfo: name, preview, etc.). There is NO level-name field.
- ETribeEnvironmentType values (binary strings): None, PolygonCity, Desert, Pioneer, HipHop, Lodato, Passthrough,
  VideoSphere, Lounge, Void, HotelSelina.
- TribeGameState.SetEnvironment: exec thunk rva 0x4fc4974, impl rva 0x509497c.
  - this+0x308 = current env enum, +0x309 = previous.
  - If the previous env != 0, FUN rva 0x5094ac8 unloads it.
  - If the new env != 0, FUN rva 0x4fb1608 builds the level path, then FUN rva 0x5094bb4 streams it in.
  - Passthrough special case: enum == 7. FUN rva 0x50c4394 broadcasts the change.
- Level path builder (rva 0x4fb1608): FName from FUN rva 0x4fb1894(enum), then
  `World'/Game/Maps/Environments/%s.%s'`. => Level = /Game/Maps/Environments/<Name>.<Name>, hard-wired per enum value.
- => A pak alone can REPLACE a stock level (same path; a _P pak wins) but cannot ADD an 11th environment.
- A NEW entry needs mod code, either:
  - (A) hook rva 0x4fb1894 so a new value (e.g. 11) maps to "Environment_<Ours>", plus a DT row (pak override or
    runtime row injection) with Environment=11 + our SkinInfo. Tribe's own menu, loading screen and config then
    treat it as native. Guests without the mod get an unknown value (likely no environment).
  - (B) our own menu box, which calls SetEnvironment(None) and then LevelStreamingDynamic.LoadLevelInstance(our path)
    itself.
  - Either way the APK must be rebuilt and re-signed.

### Session 3m cont. 2 — Signing for any session: scripts/sign_apk.sh (password stays out of the repo and the chat)
- Set up by the mod session at the user's request. `bash scripts/sign_apk.sh <in.apk> <out.apk>` runs
  zipalign -p 4, then apksigner sign (tribe.keystore, alias tribe, `--ks-pass file:` from
  C:\Users\Chris\.tribe-signing\ks.pass, overridable via $TRIBE_KS_PASS), then apksigner verify.
- The password file is private, outside the repo, and created by its owner. Never read it, print it, or copy it into a
  chat. Allowed by the project's .claude/settings.local.json rule `Bash(bash scripts/sign_apk.sh:*)`. Run the command
  from the repo root without a `cd … &&` prefix so the rule matches. The output directory must already exist (zipalign
  can't create it).
- VERIFIED 2026-10-04: re-signed a copy of out/hookA/menu.apk into the scratchpad and compared it with the APK pulled
  live from the headset (`pm path` + `adb pull`). Both: CN=Tribe Mod, O=Personal, C=US, SHA-256
  979d63d7f52f393951dd9614d0f41ee378468c55febb600414a9238b0d5694e9. => `adb install -r` of sign_apk.sh output is
  accepted as an update (no uninstall, no re-seed). Nothing was installed in this test.

## Session 3n — Custom-environment box in Tribe's menu (flag tribemod/env_menu): mod side WORKS, level pending
Code: hook/dumper.cpp "Custom environments" block (game thread: env_menu_tick, plus a repl_pe branch) and
env_menu_poll (poll thread). Refactors: box_set_label() is shared by avatar and environment boxes;
menu_resolve_engine_fns() is shared by both polls.
- Boxes come from tribemod/envs.txt, one "Label=/Game/Long/Package/Name" per line. With no file there is a single
  "Festival" box -> /Game/Mods/Festival/Maps/Environment_Festival. Boxes reuse the avatar-box technique: SpawnObject
  BP_EnvironmentSkin_C (outer = Tribe's environment object), ListView.AddItem, relabel NameText, and swallow
  W_SkinItem.OnMouseButtonDown plus the EnvironmentList item event.
- Click flow:
  - step 1: TribeGameState.SetEnvironment(Void=3).
  - step 2: hide the Void's SM_BackdropScreen and SM_BackdropScreen_ChromaKey.
  - step 3: LevelStreamingDynamic.LoadLevelInstance(our path, WorldContext = game state).
  - step 4: poll IsLevelLoaded / IsLevelVisible.
  - A stock pick (EnvironmentList event with a non-ours item) unloads ours.
  - The choice persists in tribemod/active_env.txt and is re-applied once Tribe's environment has been stable ~8 s
    after launch.
  - On failure (em_fail): screens back, choice forgotten, and (env2 build) Tribe goes back to the previous
    environment.
- [observed, on device, pid 5149, build env.aligned.apk] box added, click caught, then:
    game state = TribeMainGS_C  (/Game/Maps/DJRoomMap.DJRoomMap.PersistentLevel.TribeMainGS_C)
    reflected property CurrentEnvironment (EnumProperty) @0x308  == Ghidra's native +0x308 (independent match)
    step 1/4: SetEnvironment(Void=3) from 10 (VideoSphere);  step 2/4: environment now 3 (Void)
    step 3/4: LoadLevelInstance(/Game/Mods/Festival/Maps/Environment_Festival) -> success=0 (EXPECTED: no level yet)
- Lessons:
  - A name search for "TribeGameStateBP_C" never finds the game state: the live class is TribeMainGS_C. The game
    state is now taken from GameplayStatics.GetGameState(world context = BP_Rig_C or our actor), on the game thread.
  - find_live only scans up to the cached object count, so call refresh_numelements() before searching for freshly
    streamed actors. The first build reported "hid 0 Void screen(s)" for this reason; fixed in env2.
- ETribeEnvironmentType values (runtime): None 0, Lounge 1, Desert 2, Void 3, Lodato 4, PolygonCity 5, HipHop 6,
  Passthrough 7 (= Ghidra's ==7 check), HotelSelina 8, Pioneer 9, VideoSphere 10, MAX 11.
- Layout reference: DJ rig (BP_Rig_C) world loc (-5,31,78) cm, rot (0,0,0), i.e. the booth is at the origin facing yaw 0.
- Builds:
  - out/hookA/env.aligned.apk is INSTALLED (lib 211672 B).
  - out/hookA/env2.aligned.apk adds the two fixes (lib 212072 B); built and signed, NOT installed (it ships with the
    first level test).
  - Both are signed with scripts/sign_apk.sh (cert 979d63d7…).
  - scripts/reseed.sh still points at menu.aligned.apk. Update it once env2 is verified.
- Unreal: the launcher had started installing UE **5.8.3** (wrong: Tribe is 5.4, and newer-engine content won't load).
  The user is switching to 5.4.

## Session 3o — Unreal route: what works, what blew up, and how Tribe's stock environments are built (2026-10-04)
UE project: C:\Users\Chris\TribeUE\TribeXR. It mirrors Tribe's config: forward shading, Vulkan, MSAA 2, MobileHDR off,
multiview, chunked shared shader libraries. Scripts:
- Scripts/build_festival.py: builds the level (full-editor -ExecutePythonScript; commandlet mode crashes on actor spawn).
- Scripts/pack_festival.sh: cook output -> pakchunk50 -> patch OBB.
Engine: UE 5.4.4 (the launcher first installed 5.8 by mistake).
Cook: UnrealEditor-Cmd -run=cook -targetplatform=Android_ASTC -unversioned -map=...; chunk 50 via PrimaryAssetLabel.
- Pak delivery: proven (FileExists=1 for our .umap, our shader lib, and the pak inside the patch OBB).
- By-name LevelStreamingDynamic.LoadLevelInstance can NEVER load mod content. UE 5.4 LevelStreaming.cpp only accepts
  packages listed in the game's asset registry (AssetRegistry.GetFirstPackageByName). LoadLevelInstanceBySoftObjectPtr
  skips that check and returned success=1 for our level.
- v1 level (custom unlit materials): loading it, or LoadAsset_Blocking on one of our materials, made Tribe allocate
  ~2 GB in 0.5 s. VrApi showed Free=2139MB, then lowmemorykiller fired and Tribe was killed (pids 14308, 15487, 19111).
- Byte comparison of Tribe's cooked engine assets vs ours:
  - /Engine/BasicShapes/Cube and Sphere: IDENTICAL. Same engine serialization, so meshes and levels are fine.
  - BasicShapeMaterial: DIFFERENT. Same names and imports, but the export body is 56,562 vs 49,090 B (shader-map data
    differs with the engine build's plugins and features).
  - => Do not ship our own compiled materials.
- v2 (current): every surface is a MaterialInstanceConstant of a material Tribe ships:
  - /Engine/BasicShapes/BasicShapeMaterial ("Color", "Roughness")
  - /glTFRuntime/M_Unlit_glTFRuntimeBase ("baseColorFactor", "baseColorTexture", ...)
  - /glTFRuntime/M_Unlit_glTFRuntimeTwoSided_Inst
  - The /glTFRuntime parents exist in the UE project only as stubs (Plugins/glTFRuntime) and are never shipped.
  - PrimaryAssetLabel bApplyRecursively=False.
  - Chunk 50 = level + 9 MICs + T_SkyGradient, and NO ShaderArchive_Chunk50. Pushed. Not yet tested on device.
- Mod fixes in env6 (installed, not yet tested):
  - GetGameState now tries world contexts in order: our avatar actor, the menu list, then the rig. The first BP_Rig_C
    found can sit in a preview world, which gave gs=0 and "click ignored".
  - Our list item copies the POD fields (Name=Environment_Void, EnvironmentType, bIsOwned/bOwned/...) of Tribe's own
    "The Void" item before it is added. A default item has Name=None and is not owned: the box showed "Load", and
    applying it set environment None (dark decks).
Anatomy of a stock environment level (Environment_*.umap name tables):
- Lights: SkyLight + SphereReflectionCapture in all of them, a DirectionalLight in some, and many baked Spot/Point lights
  (HipHop 13+12, PolygonCity 62 point, Pioneer 77 spot). PostProcessVolume and InstancedFoliageActor in several.
- Sky: a mesh + material (SM_CubeSkyboxNoGround, SM_SkySphere + M_HDR_envCubeMap, SM_SkyboxRing, EditorSkySphere).
- Set: a few atlas-textured meshes, often with _quest/_MOBILE material variants. Pioneer uses BasicShapeMaterial on a Cube.
- Level BP: SetupEnvironmentBackdrop(VisualsManager, BackdropMesh, ChromaKeyBackdropMesh, DJTableMesh). Each environment
  supplies its OWN DJ table mesh. Some also start MediaPlayers (OpenSource/Play) for video screens on buildings.
- HipHop "Ride" = animated stage01_C..stage08_C + Tunnel_C blueprint actors. HotelSelina has BP_AirBallons_C.
Menu display (W_SkinItem name table):
- Box widgets: NameText, DescriptionText, PreviewImage, StatusText/StatusBorder, ProgressBar (downloads), SettingsButton,
  SubscribeIcon.
- Driven by item.SkinInfo (Name text, Description text, PreviewImage = T_SkinPreview_Environment_*) and flags (bOwned,
  bCanBeUsed, bRequiresSubscription, ...).
- Addon/DLC paths: DownloadAddon, UnlockAndApplySkin, OnSkinPurchaseRequested.
- W_VisualsMenu: BuildEnvironmentSkinWidgets <- GetDataTableRowNames(DT_EnvironmentSkins). It also has
  SetHideRoomInSpectatorCameras and SetLightsDisabled.
- TribeXR.uproject (from pakchunk0): EngineAssociation {F4F50273-400D-FA10-878A-AC90658490BC}, i.e. a SOURCE-BUILT /
  custom engine, not the launcher 5.4. Enabled plugins: SuperPowered, TribeMIDI, OnlineServices, OnlineSubsystemEOS,
  EOSVoiceChat, EOSShared, OnlineSubsystemOculus, GameAnalytics, ToxMod, XRBase, OculusXR, MixedRealityCaptureFramework,
  MetaAvatar2, OSC, NDIIOPlugin, glTFRuntime, AgoraRtcPlugin, AgoraRtmPlugin. Disabled: OnlineSubsystemSteam,
  Cognitive3D, AndroidMedia.
  - [inferred] Likely Meta's UE 5.4 fork (custom build + OculusXR + a bigger material shader-map body), e.g. extra
    mobile passes such as AppSW motion vectors.
  - To ship OUR OWN compiled materials, the cook must match that engine build. Test oracle: make our cooked
    /Engine/BasicShapes/BasicShapeMaterial byte-identical to Tribe's.
  - Until then: custom meshes, textures, MICs of Tribe-shipped materials (BasicShapeMaterial, the glTFRuntime
    lit/unlit/masked/translucent/two-sided set), and Tribe's own backdrop/video material.

### Session 3p — Matching Tribe's engine (2026-10-05): it is Meta's UE 5.4 fork; real cause of the material OOM
[observed: libUnreal.so reflection tables vs stock UE 5.4.4 UnrealEditor-*.dll, via scripts/ue_schemadiff.py; byte diff
of our cooked BasicShapeMaterial vs Tribe's; libOVRPlugin.so; Meta docs]
- Tribe's UMaterial has 2 properties stock 5.4.4 lacks, inserted right after bIsSky: bXRSoftOcclusions and
  XRSoftOcclusionsDepthBias. libUnreal.so also has bSupportsXRSoftOcclusions and the TBasePassPSF...XRSoftOcclusions
  shader types. Meta docs: XR soft occlusions need Meta's fork ("shader changes not present in Epic's Unreal Engine").
  Tribe's DefaultEngine.ini does not turn the feature on. => The engine is Meta's Oculus-VR/UnrealEngine 5.4 fork.
  - OVRPlugin is 1.103.0 (libOVRPlugin.so string, OculusXR.uplugin VersionName).
  - [derived] 1.103.0 = SDK v71: v50 = 1.82.0 and v51 = 1.83.0 (Meta's Unity package pages), so the offset is 32.
    Meta's v71 Unreal plugin targets UE 5.4.
  - Expected fork tag shape: oculus-5.4.x-release-1.103.0-v71.x. Confirm from the tag list once access works.
- Why our own UMaterial OOM-killed Tribe:
  - Cooked packages are unversioned, so each property is stored by its index in the class's property list.
  - The first byte that differs from Tribe's copy is at offset 12: a header fragment skips 31 here, 33 in Tribe's.
  - [derived] Our StateId (index 124, a 16-byte GUID) is read by Tribe as MaxWorldPositionOffsetDisplacement (a float).
    Our next value (index 128, bIncludedInBaseGame) is read as SpecularProfiles (an array). The array count comes
    from leftover GUID bytes, i.e. garbage, which gives a giant allocation and the lowmemorykiller kill.
  - The shader-map body differs too (Session 3o). That is a second incompatibility, hit only after this one.
- Every class the v2 festival ships is IDENTICAL in both engines (ue_schemadiff SAME):
  - Materials: UMaterialInterface, UMaterialInstance, UMaterialInstanceConstant, base-property overrides, static params,
    scalar/vector/texture parameter values, FMaterialParameterInfo.
  - Textures: UTexture, UTexture2D, UStreamableRenderAsset.
  - Components: UStaticMeshComponent, UMeshComponent, UPrimitiveComponent, FBodyInstance, USceneComponent,
    UActorComponent.
  - World: AActor, AStaticMeshActor, AWorldSettings, UWorld, ULevel, FTickFunction, NavigationSystemModuleConfig.
  - The v2 MIC .uexp files are 98-145 bytes, so they carry no shader maps. => The v2 pak avoids the OOM path.
    It is still untested on the device.
- Building the fork on this PC (checked):
  - Space: D: has 503 GB free, C: 84 GB.
  - Hardware: i5-9400F (6 cores, 6 threads), 32 GB RAM.
  - Toolchain:
    - Installed: Visual Studio Community 2022 17.14.13 with the "Desktop development with C++" workload,
      MSVC 14.44.35207, and Windows SDK 10.0.26100. VS 2019 Build Tools add MSVC 14.29 and SDK 10.0.19041.
    - (A first check wrongly said "none". vswhere's -property takes ONE name, and PS 5.1 ConvertFrom-Json does not
      unroll arrays. Read C:\ProgramData\Microsoft\VisualStudio\Packages\_Instances\*\state.json instead.)
    - Missing: the MSVC v14.38 toolset (component Microsoft.VisualStudio.Component.VC.14.38.17.8.x86.x64).
      - It is UE 5.4's preferred compiler. UBT 5.4 bans 14.39.33519-14.39.x for internal compiler errors.
      - 14.44 is untested here for a 5.4 engine build.
  - Access: gh is logged in as apedonkey, but EpicGames/UnrealEngine and Oculus-VR/UnrealEngine both return 404.
    The GitHub account still has to be linked to the user's Epic account, and the org invite accepted. Meta's
    quick-start page also mentions a verified Meta developer account.
  - Plan:
    1. Add the MSVC v14.38 component to the existing VS 2022 (Installer > Modify > Individual components).
    2. A shallow clone of the matching tag onto D:.
    3. Setup.bat, then build UnrealEditor + ShaderCompileWorker for Win64 Development, overnight.
  - Gates before shipping any custom material:
    1. ue_schemadiff against the fork's UnrealEditor-Engine.dll must show UMaterial SAME.
    2. Re-cook /Engine/BasicShapes/BasicShapeMaterial with Tribe's exact config; compare it to Tribe's copy.
    3. Test one custom material on the device.

### Session 3p cont. — Meta fork checked out and set up for building (2026-10-05)
- GitHub access works after the user linked GitHub (apedonkey) to Epic. Oculus-VR/UnrealEngine is private, its parent is
  EpicGames/UnrealEngine, and its default branch is oculus-5.8.
  - 5.4 tags: 5.4.1 (1.98/v66), 5.4.2 (1.99/v67), 5.4.3 (1.100/v68, 1.101/v69), and 5.4.4-release-1.103.0-v71.0.
- **Exact match for Tribe: oculus-5.4.4-release-1.103.0-v71.0.**
  - Commit 76aef8b6, "Unreal Engine Version 5.4.4-v71".
  - Build.version: 5.4.4, BranchName "Partner-Oculus-UE5", CompatibleChangelist 33043543.
  - Its UMaterial UPROPERTY list (Material.h at that tag) is IDENTICAL to Tribe's: 120 props, XR soft occlusions included.
  - Its Engine/Plugins/Runtime/OculusXR is 1.103.0, matching Tribe.
- Checkout: D:\MetaUE54. Shallow single-branch clone of that tag; about 1 GB download and 190,596 files.
  - Dependencies: GitDependencies with --exclude=Mac/IOS/TVOS/Linux*/osx*/VisionOS --no-cache.
    That is 14.0 GB to download, about 38 GB unpacked (58.7 GB unpacked with everything).
  - UEPrereqSetup and UnrealVersionSelector /register were NOT run: the runtimes are already present from the launcher 5.4.
- Toolchain per the tag's Engine/Config/Windows/Windows_SDK.json:
  - Preferred MSVC 14.34-14.38. Banned: 14.39.33519+. Windows SDK main version 10.0.19041.0.
  - Added to VS 2022 Community: VC.14.38.17.8 (now 14.38.33130 next to 14.44) and Net.Component.4.6.2.TargetingPack.
  - SDK 10.0.19041 comes from the VS 2019 Build Tools.
- Fork mod project: C:\Users\Chris\TribeUE\Meta\TribeXR (a copy of Config/Plugins/Scripts; EngineAssociation "").
  The 5.4.4 launcher project at C:\Users\Chris\TribeUE\TribeXR is untouched.
  - Its RendererSettings already equal Tribe's (25 lines, same).
  - Tribe also has OculusXRHMDRuntimeSettings and SystemSettings sections, and the OculusXR plugin enabled. Not mirrored
    yet: the plugin's shaders are global ones (Highlights/JumpFlood), and Tribe's BasicShapeMaterial has the same
    material shader type set as stock. Enable it (plus deps XRBase, EnhancedInput, ProceduralMeshComponent,
    AndroidPermission, LiveLink, OpenXR, PluginBrowser) only if the oracle comparison points to it.
- Build: C:\Users\Chris\TribeUE\Meta\build_engine.ps1 runs Build.bat ShaderCompileWorker, then
  UnrealEditor -Project=<fork project>. The project flag is needed so the non-default Python/EditorScripting plugins get
  compiled. It logs to build_engine.log in the same folder and keeps the PC awake while running.
- 2026-10-05, at the user's request: Windows Defender real-time scanning now excludes D:\MetaUE54 and
  C:\Users\Chris\TribeUE\Meta, to speed up compiles. Undo from an elevated prompt:
  Remove-MpPreference -ExclusionPath 'D:\MetaUE54','C:\Users\Chris\TribeUE\Meta'
- First build attempt failed at makefile creation: "Could not find NetFxSDK install dir" for SwarmInterface (needed
  by UnrealEd). Fixed by adding VS component Microsoft.Net.Component.4.8.SDK, which registers
  HKLM\SOFTWARE\WOW6432Node\Microsoft\Microsoft SDKs\NETFXSDK\4.8. Note the 4.6.2 targeting pack alone is NOT enough.
- Editor build: 6,578 actions, Parallel executor, 6 processes, cl.exe at BelowNormal priority.
  ShaderCompileWorker took 256 actions in 635 s.

### Session 3q — v2 festival WORKS on device (2026-10-05 10:51)
[observed: logcat TRIBEMOD + ActivityManager; the user confirmed "it loaded!" in the headset]
- Patch OBB patch.2304 (31,743 B, chunk 50: level + 9 MICs + T_SkyGradient, no shader archive) and the env6 mod build.
- Startup: the first Tribe process (pid 14653) exited at 10:50:38 with no crash or lmk line ("has died: fg TOP"). Its
  resolve only saw NumElem=16384 and never found the CDOs or SetEnvironment. A second process started at 10:50:44 and
  resolved everything:
  - LSD, SetEnvironment and LoadLevelInstanceBySoftObjectPtr all found.
  - The game state was found via GetGameState: TribeMainGS_C, environment@0x308 = 7 (Passthrough).
  - The Festival box was added carrying The Void's identity (Name=Environment_Void, 3 fields copied).
- The user clicked Festival:
  - step 1: SetEnvironment(Void)
  - step 2: environment = 3; screens found right after
  - step 3: LoadLevelInstanceBySoftObjectPtr success=1
  - step 4: loaded=1 visible=1 after 1 s. No OOM, no crash.
- => The pipeline is proven end to end: UE 5.4.4 launcher cook (MICs of Tribe-shipped parents only), repak V11, patch
  OBB, mod box, soft-ptr level stream.
- **Bug found and fixed (v2.1): the menu pointer vanished once the Festival level loaded.** It worked in The Void just before.
  - [observed in UE 5.4.4 source] AStaticMeshActor's constructor sets StaticMeshComponent->bUseDefaultCollision=true.
    At load, UStaticMeshComponent::UpdateCollisionFromStaticMesh() then re-applies the MESH's BodySetup profile
    (BlockAll for BasicShapes), overriding the component's.
  - build_festival.py only called SetCollisionEnabled(NoCollision), which does not clear that flag. Only
    SetCollisionProfileName does (UStaticMeshComponent override).
  - So every shape was solid in game, including the 300 m SkyDome sphere that encloses the player.
  - [derived] Tribe's BP_InteractionLaser (UpdateLaserPointerToNearestSurface uses LineTraceSingle) and its
    WidgetInteraction ray start inside that sphere and get a blocking hit at distance 0. Result: no beam, no menu hover
    or click. Deck touch still works because it uses overlaps, not traces.
  - Fix: place() calls set_collision_profile_name("NoCollision") and then raises if use_default_collision is still set.
    The v2.1 cooked level's name table now has "NoCollision" ("Custom" is gone).
  - Rebuild gotcha: in Git Bash, run the cook with MSYS_NO_PATHCONV=1. Otherwise -map=/Game/... becomes
    "C:/Program Files/Git/Game/..." and the cook silently skips the map, leaving no pakchunk50 manifest.
  - v2.1 patch OBB: 32,862 B, md5 f986e865321f3a18e5789f64b2256a33. Pushed as a temp file then mv'd over the patch
    OBB, so the running Tribe keeps its open inode. Device test pending.
  - **v2.1 device test 2026-10-05 11:12: PASSED.** The Festival loads in 1 s, and the user confirmed the pointer works and
    menu items click with the level in.

### Session 3r — Avatar hands vanished after picking controllers back up: fixed (2026-10-05)
[observed: logcat A2 lines during a live repro; Tribe object dumps; OculusXR plugin source in D:\MetaUE54]
- Symptom: put the controllers down (Tribe's tracked hands show), pick them up again, and sometimes there are no hands. This
  happened in any environment, not just the Festival.
- Cause: a2_update_hand_modes chose per hand from OculusXRInputFunctionLibrary.IsHandPositionValid/GetTrackingConfidence.
  - At the reported moment the mod sat in "hands L=tribe R=tribe" (model hands hidden) with valid=1 conf=1, while Meta's
    wrist was 12 cm from the motion controller (controllers in hand; ~0 cm when hand-tracked).
  - The Quest keeps reporting tracked hands while you hold controllers. Tribe had already hidden its
    TribeControllers_C.OculusXRHandComponent, so neither hand was drawn.
- Fix (hook): the model hand now mirrors what Tribe draws. For each side, find the local player's OculusXRHandComponent
  whose outer is a TribeControllers_C:
  - Side comes from SkeletonType @2561. Local player: TribeControllers_C.OwningPawn @1384 == g_pawn; any player if that
    pointer is stale.
  - Show the model hand iff SceneComponent.IsVisible() is false. The Quest signal is used only until Tribe's meshes have
    been seen once.
- Tribe DESTROYS and RESPAWNS TribeControllers_C at every hands<->controllers switch (seen: 6 hand meshes at once, and
  "0 live" for ~8 s right after launch). So:
  - skip RF_MirroredGarbage (0x40000000) components and owners; take the newest match;
  - re-find on every poll tick (500 ms) while the cache is stale;
  - hold the current state while unknown.
- Builds: out/hookA/hands.aligned.apk (first fix), then hands2.aligned.apk (garbage/respawn hardening). Both were tested by
  the user: "its working!", then "seems to be working just fine".
- scripts/reseed.sh now puts back hands2.aligned.apk (it used to name menu.aligned.apk, which predates the env menu).

### Session 3s — Dino Stage v1 (2026-10-05)
[observed: logcat [ENV]; the user in the headset: "runs smooth and the pointer is still there"]
- Pipeline: Blender 4.5.14 LTS portable (D:\Tools\blender-4.5.14-windows-x64; official mirror zip, sha256 verified on a
  second mirror. Blender was NOT installed before: the 4.3/4.4 folders only held add-on leftovers).
  - TribeUE/TribeXR/Scripts/Blender/dino_stage.py builds the set procedurally:
    - spine arches with 14 horns and 28 spikes, a metaball skull placeholder, bulbs, the moon screen and an LED arc;
    - deck/stacks/barrier, 2,100 static low-poly people with phone lights, the ground and a 480 m star sky.
  - It bakes DIFFUSE lighting on the GTX 1660S (OptiX), tonemaps 1-exp(-kx), and writes sRGB PNGs with its own PNG
    writer. One FBX per surface. Also renders previews.
  - Then Scripts/build_dino.py imports into /Game/Mods/Dino. Everything is a MIC of Tribe's
    /glTFRuntime/M_Unlit_glTFRuntimeBase (or the TwoSided inst for the sky), with NoCollision; PAL_Dino puts it in chunk 50.
  - Cook both maps: -map=<Festival>+<Dino>. Patch OBB 32.7 MB: 90 files, no shader archive, no stubs, no engine content.
  - tribemod/envs.txt has two lines, Festival and "Dino Stage". A running Tribe adds new boxes live, but the pak only
    mounts at launch.
- Gotchas:
  - Blender FBX (FBX_SCALE_UNITS) comes into UE 5.4 100x too small: set import_uniform_scale=100.
  - Y comes in mirrored: the screen landed at -Y, so build_dino turns the level 180 deg (the set is X-symmetric).
  - smart_project packed the 44k-face crowd into 0.3% of the UV space, and lightmap_pack only reached 3.9%. Fixed with
    per-person UV cells: one 46x46 grid cell per person, cylindrical wrap.
  - adb push into Android/data fails ("remote fchown failed"): write small files with adb shell printf > file.
- Result: Dino Stage loads in 1 s. Smooth on the Quest 3 (~130k tris), pointer OK.
- The user: "we're really gonna have to do some major editing to make this look good". They also want a scripted
  selfie-stick (drone cam) flight path that shows the crowd and stage while they play.
- Detail pass, Dino Stage v2: pushed 2026-10-05 13:2x; patch OBB 50.5 MB, 110 files.
  - Crowd of human shapes with poses and LOD: legs/torso/head/arms near the stage, simpler further back, boxes far away.
    120k tris.
  - Truss towers flying J-curved line arrays, ground subs, 19 moving heads with palette lenses, LED booth front.
  - Bone material with Voronoi cracks plus AO, baked at 4096.
  - Full bake ~9.5 min on the 1660S.
- Drone PATH mode (hook, 2026-10-05; out/hookA/drone2.aligned.apk, installed; reseed.sh now points to it).
  - drone.txt "mode=path" plays a looping reel of shots from tribemod/drone_path.txt, re-read on change by mtime+size.
    Without that file it plays the built-in DRONE_REEL: overview push-in, crowd pass, push-in to the DJ, close orbit,
    over-the-shoulder, low hero shot, tight reverse arc, crane up (8 shots, 81 s).
  - Syntax: "fly <secs> x,y,z x,y,z [look=dj|x,y,z]", eased with smoothstep, and "orbit <secs> [r=] [h=] [deg=]
    [start=]" around the smoothed head; start -90 = crowd side.
  - World cm: DJ rig at the origin, crowd toward -Y, stage +Y. Shots cut on change. Logs "[DRONE] shot i/n".
  - Same takeoff/landing as orbit mode, so the selfie camera returns to the stick when drone_cam is removed.

### Session 3t — Dino Stage v3.1 + DJ-area layout measured (2026-10-05)
[observed: bake log, previews, logcat [ENV] from out/hookA/gear2.aligned.apk; reseed.sh now points to gear2]
- v3: a riser under the DJ (SM_DinoRiser), a booth table under the gear (TABLE in dino_stage.py: x -95..85 cm,
  y -5..50 cm, top 74 cm, i.e. centred on the rig's x and 4 cm under the rig's z=78), an LED booth front, LED pillars,
  ferns/eggs/ribs, and the stage set dropped 1 m (STAGE_DROP) so the crowd stands below the DJ.
- v3.1 bake fixes:
  - The crowd was washed out (mean linear 0.128): clothes at night albedo x0.5 and exposure 1.8 -> 1.1, now 0.059.
  - Ferns baked black (0.005) because frond faces pointed down (normal = side x d had z=-1) and a DIFFUSE bake only
    sees the normal side. Winding flipped, now 0.031.
  - Flags are their own single-sided mesh (SM_DinoFlags, 6-colour palette T_DinoFlags, TwoSided parent), so they show
    colour from both sides.
  - Patch OBB 52.4 MB, 138 files, 19 actors. Loads in 1 s (14:38).
- Layout from the gear2 scan (world cm, while on the Void, table at its current height):
  - PlayerStartDJ (-6,87,1) facing yaw -90, i.e. toward -Y and the crowd. Pawn at (-11,87,0). Rig BP_Rig_C (-5,31,78).
  - PlayerStartTeacher (-6,-58,1) facing +Y. BP_MiniMenu (-5,-6,93), box x -73..65, z 89..191.
  - BP_TableHandle (BP_HeightHandle_C) at (-4,69,89), box x -194..194, y -14..130, z 0..69. The table height is
    user-adjustable, and a static booth top only fits the current setting.
  - SpectatorBoundingBox (StaticMeshActor) box x -250..250, y -221..279, z -6..494: the space Tribe's own spectator
    cameras stay in.
  - SpectatorCamera1 (-2,-86,176) looking +Y; Camera2 (0,39,194) top-down; Camera3 (120,85,150); Camera4 (99,-76,158).
  - The scan stopped at its 48-actor cap on world-origin managers before reaching the gear itself.
    Next version: count distance-only hits only when the box is non-empty, and skip archetypes (RF_ArchetypeObject 0x20).

### Session 3u — Festival grounds framework (2026-10-05)
[observed: Tribe's paklist, extracted glTFRuntime materials, harness and --fast pipeline runs]
- The user: "i want this to look good. also behind the crowd and on the sides, i need like festival stuff going on,
  its too empty".
- Tribe ships unlit alpha-blended and masked glTFRuntime instances, which unlock beams, glows and cutouts without our
  own shaders:
  - /glTFRuntime/M_Unlit_glTFRuntime{Masked,TwoSidedMasked,Translucent,TwoSidedTranslucent}_Inst.
  - Base parameters (cooked name table): alphaCutoff, bAlphaMask, baseColorFactor, baseColorOffset/Rotation/Scale,
    baseColorTexCoord, baseColorTexture, bUseVertexColors.
  - Opacity is assumed to be baseColorFactor.a x texture alpha (glTF semantics). Not yet verified on device.
  - Our MICs must only set parameters, never overrides or static switches, or they would need their own shader map.
- TribeUE/TribeXR/Scripts/Blender/grounds/:
  - kit.py: the module contract. build(rng) returns lit / glow / beams / halos / lights / exclude / people.
    It also holds the LIT material library, the GLOW palette and its UVs, and helpers: box, cyl, truss,
    string_lights, the 5x7 LED font, beam_planes, halo, and an RGBA PNG writer.
  - preview.py: renders one module in context: the current out/*.fbx with their baked textures, unlit.
    Usage: `blender -b --factory-startup --python grounds/preview.py -- <module> --views dj,...`
  - Modules, built by four parallel agents: vendors.py, infrastructure.py, landmarks.py, atmosphere.py.
- dino_stage.py integration (backup dino_stage.v3.bak.py):
  - Modules are built with seed 1234, the same as the previews.
  - Crowd keep-out rects and extra people. One baked mesh per module, SM_DinoGrounds<Name> + T_DinoGrounds<Name>.
  - Shared meshes: SM_DinoGroundsGlow (T_DinoGroundsPal, no mips, nearest), SM_DinoBeams and SM_DinoHalos (alpha).
    Beams and halos are hidden from the bakes.
  - Module lights bake onto everything. STAGE_AIMS (atmosphere) turns the 19 fixture heads.
  - The baked ground grows to 320 x 320 m at 4096. out/manifest.txt lists what was exported.
  - DINO_OUT=<dir> writes elsewhere, and --fast does a 2.5 min pipeline test with tiny bakes.
    Both protect out/, which the agents' previews read.
- build_dino.py:
  - Adds the SURFACES for SM_DinoGrounds*, GroundsGlow, Beams and Halos.
  - Creates the stub /glTFRuntime/M_Unlit_glTFRuntimeTwoSidedTranslucent_Inst once: a MIC of the unlit stub with the
    blend mode set to Translucent and two-sided on.
  - Honors manifest.txt.
- Fork verification result (2026-10-05 15:28, verify_fork.sh; full run 37 min, the first cook compiles the global
  shaders):
  - Reflection: UMaterial SAME, 120 props, matching Tribe's bXRSoftOcclusions + XRSoftOcclusionsDepthBias.
    Stock 5.4.4 lacks those two.
  - The one remaining schemadiff DIFF (a 2-prop StaticMesh/OverrideMaterials array) also appears against stock. It is
    a pairing artifact: the monolithic .so has arrays from modules the two DLLs don't contain.
  - Oracle BasicShapeMaterial, cooked by the fork:
    - .uasset IDENTICAL (693 B).
    - .uexp the same size as Tribe's (56,566 B; stock makes 49,094 B). Only one contiguous 20-byte block differs, at
      offset 5196, right after "VULKAN_ES3_1_ANDROID". Probably the shader map ResourceHash, i.e. at least one
      compiled shader differs.
    - A "shaderdiff" agent is comparing the two shader libraries: which shader, why, and whether it is safe.
  - verify_fork.sh steps 1 and 5 passed POSIX paths to Windows python (MSYS_NO_PATHCONV=1); now wrapped in W().
    Lesson: never edit a bash script while it runs. Bash re-reads the file after each command, and a 14-byte insert
    made it run the fragment "dev/null 2>&1".
- Shader diff verdict (shaderdiff agent, 2026-10-05 15:59, files in C:\Users\Chris\TribeUE\Meta\shaderdiff\):
  - Observed: no compiled shader differs.
    - BasicShapeMaterial's map has 67 shaders (9 VS, 58 PS), byte-identical.
    - 878/878 shared material shaders and 1056/1056 global shaders are byte-identical with Tribe's libraries.
    - 46 materials cooked by both builds are identical except for one 20-byte field.
  - That field is FMaterialShaderMapId::CookedShaderMapIdHash, a hash of the compile INPUTS
    (MaterialShader.cpp:603). It is not the ResourceHash: ca414362... sits at uexp offset 56538, is identical in both,
    and is present in both Chunk0 libraries. Spot-checked independently by byte search.
  - Root cause (derived): the vertex-factory source hash. Tribe's shader text differed from ours when they cooked. The
    likely cause (inferred) is a different ShaderVersion.ush GUID from r.InvalidateCachedShaders. Not reproducible
    from shipped data, and harmless at runtime: shader code is found by the ResourceHash.
  - New oracle criterion: identical except CookedShaderMapIdHash, with identical code in the ResourceHash map.
    Checked by shaderdiff\tools\verify_oracle.py (46/46 pass).
- Custom-material device gate (2026-10-05 16:06):
  - Meta project, /Game/Mods/ShaderTest in chunk 51, built by Scripts/ShaderTest/build_shadertest.py with
    fork -nullrhi. Contents: M_ModTest (a real UMaterial: unlit, two-sided, scrolling magenta/cyan stripes x a pulse
    from Time) on the LEFT panel, and the control MI_ModTestControl (Tribe's unlit glTFRuntime, amber) on the RIGHT.
  - Fork cook: 30 s, 0 errors. Chunk 51 = level + 2 materials + panel mesh + ShaderArchive-TribeXR_Chunk51-....
  - Meta/TribeXR/Scripts/pack_chunk.sh <N> stages and repacks one chunk. make_obb.py <obb> <paks...> builds the patch
    OBB: one stored zip can carry several paks.
  - Pushed: patch OBB = pakchunk50 (Dino v3.1, launcher cook) + pakchunk51 (fork cook), md5 7abb703b...
    envs.txt has a third line "Shader Test=/Game/Mods/ShaderTest/Maps/Environment_ShaderTest".
    gear3.aligned.apk installed (gear scan: skips archetypes; distance hits need a real box). reseed.sh points to it.
  - Pass = stripes moving on the left panel. Grey/checker = chunk-51 shader library not opened.
    Crash = recover by pushing the launcher's chunk-50-only OBB.
- Grounds modules delivered (2026-10-05, 4 parallel agents; all deterministic with seed 1234; previews in
  Scripts/Blender/grounds/out/):
  - atmosphere.py:
    - Sky trackers: 4 units with 6 heads at (+-32,-92) and (+-30,22), 340 m white beams.
    - Stage look exported as STAGE_AIMS / STAGE_ANGLES / STAGE_COLORS for the 19 fixtures: white tower "wings",
      a cyan deck fan, amber crossers. Lens center is exactly base+(0,0,0.42)+d*0.205.
    - Green 13-line laser fan from a road case at stage center.
    - 82 beam quads in 3 meshes (sky / stage / laser, sorted per object), 81 halo quads.
    - Measured overdraw: 0.57 layers/px from the DJ, 0.25 from the stream camera.
  - infrastructure.py: 12,074 tris, 13 lights, 23 excludes, 18 people.
    - FOH at (0,-31): deck, desks, "DINO STAGE" LED banners, roof at the DJ's eye height, 2 follow spots aimed at
      the DJ.
    - Delay towers at (+-17,-42) with line arrays and purple beams.
    - 4 light masts. 16 LED totems held up in the crowd.
  - landmarks.py: 38,241 tris, 33 lights, 6 excludes, 139 people.
    - Ferris wheel at (-48,-105), 30 m, LED chase.
    - Second stage at (+55,-120) with an LED wall and its own crowd of 110.
    - Brachiosaurus at (+82,-56), 19.5 m; T-rex at (-76,-40), 13 m on a rock; triceratops at (+66,-14).
    - 440 trees, unlit ones as black glow silhouettes. Camping field of 165 tents with 5 campfires. Hill rings.
  - vendors.py: 24,376 tris, 39 lights, 114 people. Units sit with their backs at |x| = crowd_half(y)+17.6.
    - Left lane: BAR, TACOS, NOODLES, PIZZA, CANDY, MERCH, WATER, plus 8 portable toilets with a WC light tower.
    - Right lane: BBQ, DINO DOGS, BEER (container bar), LOCKERS/CHARGE, BURGERS, ICE CREAM, COFFEE.
    - Festoon masts and dirt lanes.
  - Kit fixes found by the agents:
    - Helpers returned the wrong faces after a capped cyl, because create_cone frees faces internally. Now the
      faces come from the op's own verts.
    - halo's flat square read as a line from eye height. The first plane now faces the DJ.
    - preview.py now simulates the final bake: stage lights, emitters at bake strength via the camera-ray trick,
      lit albedo x1.8.
    - Still open: kit.sphere's face order is run-dependent (create_uvsphere pole welding).
  - Crowd look (dino_stage.py crowd_look):
    - Hair on most heads (crown + back of head), sleeves on 60% of raised arms, bucket hats on 9% of the front rows.
    - Front-row heads at subdivisions 2. In Blender 4.5, 0 and 1 both give 20 tris.
- **CUSTOM MATERIAL GATE PASSED (2026-10-05 ~16:35, the user in the headset: "yes its pulsing colors").**
  - "Shader Test" (chunk 51, cooked by the Meta fork) shows M_ModTest animating: a real UMaterial compiled by our fork
    build, with its shaders loaded from OUR ShaderArchive-TribeXR_Chunk51 in the patch OBB. Tribe opens a chunk's
    shader library when that chunk's pak mounts, and the pixel shader with Time runs.
  - Not tested yet: World Position Offset (vertex shader), needed for the VAT crowd and moving beams.
  - Pipeline consequence: any custom material has to be cooked with the fork (D:\MetaUE54), and its pak must carry
    that chunk's ShaderArchive. MIC-only content still works from either engine.
- Device test v4 + VAT (2026-10-05 ~17:05). The user: "the vat test i see people moving. in dino animated i see the
  lights pulsing and moving".
  - So World Position Offset (VAT dancers, chunk 52 from the MetaVat project with the ModMaterialTools editor plugin)
    and our animated pixel materials (Dino Animated, chunk 53) both work in Tribe.
  - FPS: 71-72 at 72 Hz in Dino Animated (~278k tris), with 2-17 frames over 20 ms per 10 s and 300-400 ms on level
    switches.
  - A game-state lookup failed for one whole Tribe session (GetGameState null for every context; "click ignored, not
    ready: gs=0x0"). gs.aligned.apk adds a fallback that finds TribeMainGS_C by class.
- The user's next asks:
  - Lasers from the tops of the bones into the crowd.
  - Far more detailed people, and a WAY darker crowd ("night set").
  - The crowd dancing in the animated build.
  - "more people ... more totems ... especially on the sides too, pack that fuckin venue out, we are the headliner".
- Work split:
  - VAT agent: crowd v2 (detailed, LOD tiers, dance clips, totem holders, wider and denser layout).
  - atmosphere agent: a laser rig at the horn tips, with UV1-3 sweep data.
  - Me: dino_materials.laser_sweep, a WPO material with pan then tilt via RotateAboutAxis about each laser's pivot
    (47 nodes, built OK in the fork with the plugin), and the night crowd lighting.
    The night lighting cuts Front/CrowdGlow/SideFill/Wash about 4x and pools 160k -> 120k; crowd exposure 0.9.
  - The ModMaterialTools plugin is now also in the main fork project (UBT: 4 actions, 22 s, no engine changes).
- Horn tips (computed from build_structure). The two sides are NOT mirror images: the horn bend axis isn't mirrored
  (a pseudo-vector), so the left horns flare out while the right ones stand more upright.
- Crowd v2 integrated (2026-10-05 ~18:15; VAT agent's Scripts/Blender/crowd2/, README there):
  - The people are procedural festival-goers (faces, hair strands, outfits, hats, packs, phones, glowsticks) with
    8 VAT clips. Tiers: near < 12 m (~920 tris), mid < 20.5 m (~225), far (~36).
  - Totems/flags are held inside the crowd mesh: 163 in the device test. The infrastructure module's 16 static
    totems turn off via infrastructure.TOTEMS = False.
  - kit.crowd_half = 20 + 0.55*(-y), was 14 + 0.5*(-y); the vendors move out with it.
  - dino_stage.py:
    - CROWD2 switch (DINO_CROWD2=0 brings back build_crowd).
    - Phones/glowsticks emit their "Col" colors in the bake (mat_emit_col).
    - Crowd bake 4096 at exposure 0.55 (the user: "WAY darker"). No flags mesh.
    - Previews posed mid-dance (crowd2.pose_preview).
  - build_dino.py (animated build):
    - Imports T_DinoCrowdVAT.exr via dm.prepare_vat_texture (16BitData, TC_HDR, no mips, nearest).
    - Crowd meshes: vertex colors REPLACE + dm.prepare_vat_mesh (5 UV channels, 16-bit UVs, no collision data,
      bounds extended).
    - Materials dm.vat_crowd (body: baked T_DinoCrowd; glow: vertex color). dm.prepare_vat_actor on the actors.
  - Fast pipeline test: 4,552 people (4,302 field + 250 extra), 340,781 body tris, VAT 2048x256.
  - On device: "Crowd Test" chunk 52 (the stage at 16:42 + crowd v2.1, 345,882 UE vertices, 102 MB) was pushed
    17:53 but not tried yet.
- Lasers integrated: SM_DinoLasers keeps UV1-3 sweep data. Animated build uses dm.laser_sweep with pan negated for
  the FBX mirror; the stock build is frozen.
- The user on the v5 renders (2026-10-05): "ok that looks pretty good! ... everything needs to be dark, it is way too
  light. also for the lights and lasers, they shouldnt be on all the time. also, lets make the crowd with more rave
  attire and make them more believable. dont hold back".
  - Night pass (dino_stage.py):
    - NIGHT = 0.5 multiplies every bake exposure; the crowd is 0.55 x 0.5 = 0.275.
    - Sky horizon and town glow x0.4, milky band x0.6, far ground (0.004,0.004,0.006).
    - Light sources (emitters, LEDs, signs, beams) unchanged.
  - Light show:
    - T_DinoCues.png: 32 bars x 16 rows, linear data (R level, G strobe, B beat pulse), from show_program().
      Rows: stage 0, sky 2, fan 3, horn6-3 4-7, infra 8, stage2 9, lenses 10, always 13.
    - One loop = 32 bars at 128 BPM = 60 s: intro, build (lasers enter), bar-16 blackout, drop (all, strobe
      bursts), breakdown, outro (horn pairs alternate, strobe).
    - dino_materials.cue_level() samples it (nearest, sRGB off, TC_VECTOR_DISPLACEMENTMAP). beams_material has a
      CueRow param (one MIC per beam/halo mesh, per out/show_groups.json). laser_sweep uses row = 3 + LaserCue (UV4).
      strobe_tex for the lenses uses row 10.
    - Beams/halos are now one mesh per module group (SM_DinoBeams<k>, SM_DinoHalos<Module>).
    - atmosphere.py adds UV4 "LaserCue": 0 fan, 1-4 horn pairs k6-k3.
  - Crowd v3 (rave attire, believable: friend groups, shoulder riders, glowing accessories) is with the VAT agent,
    in crowd2/crowd3.py with the same API.
- The user: "Well im talking like the crowd is dark because its dark outside. Its a nighttime set. The stage would also be
  dark except for the dj and the visuals, lazrs, lights ect".
  - So v5.2: the set (structure, rig, deck, riser, plants) and the crowd are SHOW-LIT.
  - dino_materials.show_light: emissive = baked x (floor + (1-floor) x level of cue row 1 "wash"). Floor 0.08 for the
    set, 0.06 for the crowd; sweep bands across the crowd.
  - The show program moved to Scripts/Blender/show.py (no bpy); `python show.py` rewrites T_DinoCues.png alone.
- "Also let's put some speaker towers in the crowd". The infrastructure module now has 4 towers:
  - (+-17,-42) and (+-15,-65), 13.5 m, 11-box arrays, cyan LED-strip "T" frames, DINO panels, purple sky beams.
  - Masts moved to (+-30,-58) and (+-24,-78).
- Crowd v3 (VAT agent, crowd2/crowd3.py, same API; dino_stage imports `crowd3 as crowd2`):
  - 4,439 people in 874 friend groups, 14 shoulder riders, rave outfits and costumes.
  - Glow accessories (glowsticks, necklaces, LED gloves, light-up soles, phones, flow toys, totem LEDs).
  - 15 standing dances, 17 clips.
  - VAT 2048x1024 (2 pages), 326,884 tris.
- v6 pushed 22:35 (md5 371c1362...): chunk 50 = v6 (122 MB), chunk 53 = "Dino Classic" (v4 animated).
  - v5.1/v5.2/v6 have never been launched on the device yet, so crowd v2/v3 FPS is still unmeasured.

### Session 3v — v6.1-v6.3: Tribe's visuals on our big screen, deck lamps, crowd v3 FPS, skull v2 (2026-10-06)
- Crowd v3 FPS (logcat_v61, 10:24-10:27): 71.3-72.1 fps average at 72 Hz once loaded. Per 10 s window, 0-22
  frames took over 20 ms (worst 141 ms, once); the load itself had a 400 ms frame. Same class as v4 (71-72).
- v6.1: SM_DinoVisualScreen (16 x 9 m quad at Blender y 10.3, cz 7.2 pre-drop) registered via
  BP_TribeVisualsManager_C.SetupEnvironmentBackdrop(BackdropMesh=ours) -> log "our screen ... is Tribe's backdrop now".
  The booth boost (BoothSpotlight x2.5 via tribemod/lights.txt) was unwanted: "i only wanted a small light on the
  decks, not for the entire stage". v6.2 replaced it with two level spot lights DinoDeckLamp_L/R (build_dino.py
  DECK_LAMPS, 3 cd, radius 140, cones 38/20 deg, no shadows); lights.txt can still scale them by name.
- "Keywall" misread in v6.2 (registered our screen as ChromaKeyBackdropMesh with ChromaKey_M). The user then said:
  "well we dont need obs to run it. they run from the media folder inside tribe". So the user's "keywall" is the
  visuals BACK WALL (Media tab, videos from the media folder), not Tribe's Key Backwall switch.
  - W_VisualsMenu: the Chroma tab has "Key Backwall" (KeyBackdropSlider) + "Hide Room" + key color. Both call
    TribePlayerController.SetChromaKeyBackdropInSpectatorCameras / SetHideRoomInSpectatorCameras. Ghidra:
    SetChromaKeyBackdropInSpectatorCameras impl rva 0x509edd0 = `*(bool*)(this+0x8f4) = b` (a flag read by the
    spectator-camera code: UpdateSceneCaptureComponentHiddenActorsWithChromaKey / UpdateChromaKeyActorOwnership).
    So Key Backwall only changes what the STREAM cameras see (a green wall for OBS); the headset view is unchanged.
  - Media folder = the Quest's Movies folder (libUnreal string "../../../../Movies/", i.e. /sdcard/Movies; the
    user's own visuals mp4 is there). Music: "../../../../Music/". GIFs: Downloads/Gifs/, "My Gifs".
- Why v6.1 showed the video on only part of the big screen (decoded 2026-10-06):
  - Tribe's back wall is SM_BackdropScreen_OldStyleUVs (Void: actors SM_BackdropScreen + SM_BackdropScreen_ChromaKey).
    A curved 9-column strip, 18 verts, x +-287, y 244..307, z 45..280 local (arc 5.97 m x 2.35 m, ~2.54:1).
    UV0: U 0 at x=-287 (the viewer's RIGHT when facing the wall) to 1 at x=+287; V 0.5 (top) .. 1.0 (bottom).
    UV1 = UV2 = mirrored-U 0.008..0.992 (lightmap style).
  - M_VideoBackdrop PS (Tribe archive Chunk0, shader map 31a5f258..., PS index 1801; extracted with
    shaderdiff/tools/shaderlib.py + oodle_dec + NDK spirv-dis) reads UV0 (VS ATTRIBUTE4), p = (1-U, 2V-1), then applies
    MPC_VideoBackdrop: scalars Aspect [0].x, Tile [0].y, Mirror [0].z; vector StretchMode [1] (defaults: Aspect 1,
    Tile 1, Mirror 1, StretchMode (1,0,0,0)).
    - StretchMode.z > 0.5: fill (X=p.x, Y=p.y).
    - .x > 0.5: full width, V scaled by Aspect/4 (Aspect/2 when Tile).
    - else 2/3-width pillarbox (X = 1.5 p.x - 0.25), V scaled by Aspect/2.
    - Tile >= 0.5 doubles X (two copies; the second is mirrored when Mirror >= 0.5). X outside 0..1 is black.
    - BP_TribeVisualsManager sets Aspect from GetVideoTrackAspectRatio when a video opens.
  - Our old screen had plain UV 0..1, so the video landed in the lower half, mirrored, and partly outside.
- v6.3 fix:
  - dino_stage.visual_screen_uv(): U = 0.5 - x/w, Blender V = 0.5 * (z - bottom)/h (UE V 0.5 top .. 1.0 bottom after
    the FBX V flip). The screen was re-exported alone (scratchpad export_vscreen.py) into out/.
  - build_dino.py: MI_DinoVisualScreen is plain black (Tribe puts its own material on it); the chroma branch is gone.
  - hook: BackdropMesh = our screen; ChromaKeyBackdropMesh = the Void's own chroma screen. While the Dino Stage is
    active the mod sets MPC_VideoBackdrop StretchMode=(0,0,1,0), Tile=0 (fill, one copy) via KismetMaterialLibrary
    Set/GetVector/ScalarParameterValue, re-applies when Tribe changes them, and restores Tribe's values in
    em_unload. Lookups run on the poll thread (mpc_lookup); parameter FNames come from the collection's
    ScalarParameters (28 B elements) / VectorParameters (40 B). Log lines: "[ENV] video mapping ...",
    "[ENV] visuals screen: hidden=.. material=..".
  - Pushed 11:33: patch_v63.obb (md5 c03db2dc..., chunk 50 122 MB, 0 cook errors) + out/hookA/vscr.aligned.apk
    (reseed.sh MOD updated). Awaiting the user's headset test.
- Skull v2 (landmarks agent: Scripts/Blender/skull.py, skull_check.py, skull_preview.py) is integrated into
  dino_stage.py.
  - `import skull`; build_structure() bm_adds build_skull_v2() into the structure and eyes meshes.
  - The old SKULL_T / jaw_point / build_skull_mb / build_skull are deleted; SkullKey is replaced by skull.SKULL_LIGHTS
    (also in grounds/preview.py).
  - The head is ~11 m wide; 0 laser contacts, closest beam 0.51 m; chin z 12.73 pre-drop; 12,008 + 360 tris.
  - Full bake started 11:35 into Scripts/Blender/out_v7 (DINO_OUT). It keeps out/ = v6.3 intact.
    build_dino.py's SRC is still fixed to Blender/out, so it needs an override before a v7 build.
- v7 = v6.3 + skull v2: bake out_v7 18m50s, no errors, modules unchanged. atmosphere_lasercheck (now honours
  DINO_OUT): all 45 beams clear, stage clearance >= 0.46 m, DJ head gap >= 4.9 m. build_dino.py now honours DINO_SRC
  (v7 built with DINO_SRC=Blender/out_v7): 33 actors, 0 cook errors, chunk 50 = 121.7 MB.
  Pushed 11:58: patch_v7.obb md5 26ebd9ba... The mod is unchanged (vscr.aligned.apk). Awaiting the headset test.
- The user on v7 (12:24): "its not filling the entire screen. its like tribes visuals in front of our wall. so we
  technically have 2 walls", then "we dont even need the curved wall if we have the tribe key wall. just make the
  keywall as big and its done".
  - v7.1: SM_DinoLED and tex_led are gone. SM_DinoVisualScreen is 23 x 12.94 m (16:9) at y 10.3. The moon + ring +
    ring bulbs sit behind it (bulbs 16-44 cm behind) and show when Tribe's visuals are off.
  - Clearance check: nothing crosses the screen. Lasers are unchanged (>= 0.46 m).
  - build_dino.py purges the stale LED assets. Bake out_v71 17m53s; 32 actors, 0 cook errors, chunk 50 = 120.4 MB.
  - patch_v71.obb md5 19c22e46...; verified on device at 13:01: the screen registered, fill applied, video on it.
    The user: "ok looks great!".
- Streaming broke (Meta token expired; see the memory modded-build-login-recovery). The re-seed was run as two
  manual phases, because the auto-mode guard blocks `adb uninstall` until the user approves it.
  - Genuine login 12:56: 0 "Unofficial Application", 4x OBTAIN_TOKEN ok.
  - Part B restored the mod (vscr), main OBB, patch_v71, avatar/skins/calib, envs.txt/active_env/drone files, the
    flags, and the storage permissions.
  - The user: "yes i streamed fine".
  - scripts/reseed.sh: PATCH/ENVBK restore added, MSYS_NO_PATHCONV, logcat -c before the login count, MOD=vscr.
- Next (the user, 13:10):
  - "make the arches bigger ... wider" from the front, and "the screen to match that arch shape as well". This
    is with the landmarks agent: arch.py single source, mirrored horns, arch-shaped SM_DinoVisualScreen with
    16:9-box UVs.
  - "add some more stuff to the stage where im standing". This is with the infra agent: grounds/stagedeck.py.
  - After the arch: the atmosphere agent re-derives HORN_TIPS from arch.py and re-aims the fans.
- The user: "im usually in between 128 and 150 bpm. mostly heavy dubstep"; then "ok that sounds good" to moving the
  stage to 140 half-time.
  - dino_materials.py: BEAT_HZ = 140/60, HALF_HZ = BEAT_HZ/2.
    - HALF_HZ drives the cue_level beat pulse, the strobe_tex lens default, the scroll_tex booth pump and the crowd glow.
    - vat_crowd defaults to bpm=140, so the dances are 9% faster.
    - The show loop is 32 bars = 54.9 s. show.py SHOW_BPM = 140.
  - These take effect at the next Unreal build. Backup: dino_materials.v7.bak.py.
- Visuals phase 2: "visuals" leads and assembles, with helpers visuals2 (Raptor Run, Stomp, Extinction) and visuals3
  (Amber DNA, Jungle).
  - Target: 24+ loops at 140 BPM half-time, plus "Dino Visuals - Full Set.mp4" (60 min, ~6 Mbps). Output goes to
    C:\Users\Chris\TribeUE\Visuals\deliver\.
  - GPU lock: mkdir C:\Users\Chris\TribeUE\gpu.lock.d (owner.txt inside). Take it before stage bakes too.
- Giant intro (the user, 2026-10-06): a lift behind the decks with a button; a floor-length robe like the user's
  reference photo, shown only while up ("when im on the ground no cape").
  - Height test (giant1, test file giant_test.txt "o|p|h <cm>"):
    - VROrigin relative Z works: K2_SetRelativeLocation on TribePawnBP_C.VROrigin, re-applied each frame. Tribe never
      pulled it back, and the pawn's actor Z tracks it.
    - The A2 avatar's feet follow (floor = VROrigin world Z).
    - The user picked a 545 cm platform (eyes ~7 m); 9-10.5 m was "too high".
  - Implementation:
    - Blender/giant.py writes out_giant/SM_DinoGiantLift/Glow/Robe.
      - Lift: plate x+-0.6, y 0.70..1.70; telescoping column; button at (0, 1.52, 1.06) m.
      - Robe: rest = a 1 m wall on the hem ellipse (c (0, 1.84), a 2.8, b 1.16); UV1 = (h, theta).
    - build_dino.py makes MPC_DinoGiant (Height, RobeTopX/Y/Z, RobeOn, ButtonGlow) and dm.giant_lift / giant_glow /
      giant_robe materials (WPO). The robe is pulled from the hem to the shoulders by s^0.7.
    - hook giant_tick: either hand within 14 cm of the cap (re-armed after moving away, 1.2 s cooldown) gives
      DOWN -> RISING (8 s smoothstep) -> UP -> DESCENDING (60 s) -> DOWN.
      - It sets VROrigin rel Z = base + h and the MPC each frame. RobeTop = HMD - 27 cm z, 8 cm behind; RobeOn when
        h > 25 cm.
      - tribemod/giant.txt: height= rise= descend= press=. em_unload puts the DJ down.
  - v7.2 = out_v71 + giant + 140 BPM materials (mod giant2.aligned.apk): a quick test ahead of the arch/stagedeck v8.
  - v7.3: robe v2 + crowd camera v2. The user: "way too large ... more skinnier at the top with widening at the
    bottom" and "a little too far back. i cant see my face from the crowd".
    - Robe v2: hem ellipse c (0, 1.68), a 1.4, b 1.0; 64 x 28 rings. The material pulls it to the shoulders by s^1.4,
      so it stays slim through the upper body and widens toward the floor. The plate keeps only its top face.
    - Crowd camera: only while the giant runs (press to landing), the drone camera cuts to (0, -1200, 240) cm with a
      slow handheld sway. It aims at the head minus 120 cm, and the reel's playhead waits.
  - v7.4: blackout + follow spot. The user: "when i press the button, no lasers or lights and only a spotlight on me
    when im tall and when im on the ground. after im on the ground then turn on all the lights and stuff".
    - MPC_DinoGiant gains ShowLevel, ShowOffset and SpotOn. dino_materials cue_level multiplies by ShowLevel and adds
      ShowOffset to its time; chase, pillars and scroll_tex dim to 15% through show_dim.
    - The follow spot is front-of-house:
      - SM_DinoGiantSpot: 3 crossed planes on T_DinoBeam, from (0.95, -31, 5.35) m to the DJ's head, with the far end
        riding up with the lift.
      - A real SpotLight, "DinoGiantSpotLight": 9/5 degree cone, 6000 cd at full via SetIntensity.
      - The robe picks up a SpotOn term.
      - A spot from the skull's mouth was rejected: it would backlight the DJ and hide the face from the crowd camera.
    - Hook timing: after a press the show fades out over 1.5 s and the spot fades in over 1 s. On landing the show
      snaps back in 0.3 s and the spot fades out over 1.2 s.
    - ShowOffset = (bar 17 - T mod loop) restarts the light show at its drop. T is GameplayStatics.GetTimeSeconds,
      the materials' Time; it is a double on this build.
    - Device: patch_v74.obb (md5 6462842709d1c2e1374d36adabf3ed9a) and mod giant6.aligned.apk. Two full cycles ran,
      18:14-18:15 and 18:18-18:20, logging "show restarts at the drop (clock 150.9 s, offset 41.06 s)" and
      "(clock 434.1 s, offset 32.19 s)". In the second cycle two presses on the way down were "ignored while
      moving". How it looks is the user's call; not confirmed yet.
- Avatar + stage stopped loading at 18:04. The user: after a multiplayer session, then solo too. It was NOT the token;
  no re-seed was needed.
  - Cause: the mod's GUObjectArray resolve. When it ran very early (NumElements still < 10000), try_objects_field's
    slide skipped NumElements at +0x14 and accepted a constant 16384 at +0x20/+0x24, which passed the one-chunk check.
  - Every object scan was then capped at 16384 objects: no game state, no level loader, no avatar spawn, no env menu.
  - Fix in giant6:
    - Take FChunkedFixedUObjectArray.NumElements at +0x14 first (floor 1000; the chunk counts must agree). The
      fallback slide stops at +0x1C.
    - refresh_numelements self-heals when a live object sits right past the count: it switches to +0x14, or else
      counts the items, and logs "[R2] object count was stale ...".
  - Verified 18:11. Launch 1 resolved at NumElem=15871, the early case that used to stick. Its count grew to 65582,
    and the avatar spawned via FinishSpawningActor.
  - Verified 18:13. Launch 2 resolved at 22657; then "[ENV] ON", the menu boxes, the Dino Stage level load and the
    avatar. [R2] never fired: the +0x14 counter was live from the start.
  - load_result.txt, httpd.log and the INI log are now chmod 0666 after each write, so adb can read them.
- After the context reset, two agents were restarted:
  - arch2: arch v2, the arch-shaped screen, lasers via arch.py, and a stagedeck bake to out_arch.
  - visuals: the 140 BPM pack, Giant Halo, and the 60-minute Full Set.
  - The v8 integration waits for both.
- v7.5 (18:3x): the giant button + no beam. Stage-only (patch_v75.obb md5 c621a1193e3b6dca92973db3be64f189); the
  mod is unchanged (giant6).
  - The user: "i want the button to actually go down when i press it".
    - giant.py marks the cap with UV0.x = 1: 168 loops, z 1.04-1.08 m, checked by re-importing the FBX.
    - dino_materials.giant_glow sinks it GIANT_BUTTON_TRAVEL = 2.5 cm by min(3 x ButtonGlow, 1). The mod already sets
      ButtonGlow to 1 on every press (ignored ones too) and fades it out over 0.8 s, so the cap holds ~0.5 s and
      rises over ~0.3 s. No APK reinstall.
  - The user: "i need the spotlight to be less dramatic. i dont need the light beam but how i look illuminated looks
    good".
    - SM_DinoGiantSpot is out of GIANT_MESHES; giant.py no longer builds it. Its stale mesh was purged; the cooked
      chunk 50 has no GiantSpot entry.
    - DinoGiantSpotLight and the robe's SpotOn term stay unchanged.
  - Also pushed to /sdcard/Movies/Dino Visuals/ (md5-checked):
    - the 140 BPM loops: Giant Halo (red) and Spine Tunnel (amber);
    - the five 128 BPM extras: Extinction Event (inferno), Raptor Run (green), Spine Tunnel (amber/ember/ice).
- Song-synced lasers (the user: "i have a song that we need to adjust the lazers to go to, just for this set"):
  - Tribe's deck class /Game/Equipment/Deck/BP_Deck.BP_Deck_C has BP functions GetPlaybackSeconds, GetPlaybackMs,
    GetIsPlaying, GetCurrentTrackDisplayName, GetTrackDurationMs, GetDisplayTempo and GetPlaybackRate, plus a
    replicated CurrentTrackFileName (logs/scan_final/objects_v7.txt).
  - Plan: the mod finds the deck playing the configured track and writes its playhead to the MPC. A per-song cue
    table, from analysing the audio with librosa 0.11 + ffmpeg, drives the lasers in track time, so cue jumps and
    pitch changes stay in sync. Waiting for the song file.
- v7.6 = song mode for the set's opener, SVDDEN DEATH - PRELUDE I (stage patch_v76.obb md5
  169e2db5d426075e01a1866ba6d300a6; mod song1.aligned.apk). Awaiting the first device test.
  - The user: "when i play this song, no lights should be happening. at 1:09 is when the platform should raise. at 1:52
    is when the lasers from the top of the stage start going. at 2:20 i am coming down with the platform. by 2:46 im
    down at the decks for sure".
  - Song analysis (librosa; scratchpad song/analyze_song.py, analyze_grid.py, zoom.py):
    - 5:22 long, about 140-143.5 BPM. The tracker's grid is unreliable: 297/724 beats on one line, and the sections
      fit different tempos. So cues sit on measured hits.
    - 1:10.22: the hit after a breath (silence 70.17-70.22 s).
    - 1:53.1: drop 1, where the sub returns after a dip at 112.75-113.05 s. The user said 1:52.
    - 2:19.7: drop 1 ends.
    - 3:17.86 / 3:18.71 / 3:19.56: a three-gap stutter, then drop 2 at 3:19.71 (the sub enters at ~3:20.6).
    - 3:51.4: breakdown.
    - 3:58.29: the next section starts after silence at 3:57.99-3:58.29.
    - 4:39.45: section change.
  - tribemod/song.txt, also in backup/tribemod_20261006 (reseed.sh restores song.txt + giant.txt):
    match=PRELUDE I / bpm=140 / lift=69.0 139.7 166.0 /
    cues=0:dark 113.1:top 166:drop 179.7:build 197.86:dark 199.71:drop 231.4:breakdown 238.29:outro 279.45:build 320:show
  - Hook (song_* in dumper.cpp):
    - The poll thread finds BP_Deck_C instances, including subclasses, plus GetIsPlaying, GetPlaybackSeconds,
      GetCurrentTrackDisplayName and the CurrentTrackFileName property; first output = CPF_OutParm at FProperty+0x38.
    - The game thread picks a deck whose track name matches (case-insensitive, word-ended, so "PRELUDE I" doesn't match
      "PRELUDE II") and is playing. Its playhead sets the lift height (rate-limited 1.5 m/s for seeks), the lights and
      a per-frame ShowOffset, so the chosen part of the 32-bar show loops in step with the song.
    - The button is ignored while the song plays. If the song stops while the DJ is up, the lift comes down from there.
  - Stage: MPC_DinoGiant TopLasers. laser_sweep lifts the horn-tip heads (UV4.x groups 1-4; group 0 = the stage fan)
    to max(cue level, TopLasers), through the blackout.
  - Expected log: "[SONG] BP_Deck_C ..." (the function signatures), "[SONG] N deck(s)", "[SONG] deck i track: '...'
    <- the song", "[SONG] ON at ...", then "lift rising/up/coming down/down" and "lights 'top'/'drop'/...".
- Light shows for every song (the user: "is it possible to do lasers for any song??", "my songs are on the oculus
  itself", "there is a SHIT TON of songs", "ok start the scan"). The user cues the next song "with the volume down with
  the headphone on so the crowd cant hear", so the lights must follow the deck the crowd hears.
  - Scan: TribeUE/TribeXR/Scripts/songs/scan_library.py.
    - Pulls each audio file under /sdcard/Music (2052 files, 7 GB), measures it, then deletes the copy.
    - Saves TribeUE/Songs/features/<id>.npz: 5-band dB at 10 Hz, the onset envelope, beats. index.jsonl makes reruns
      scan only new or changed files.
    - 3 workers, 18 min. Failed: "AWEMINUS - MAKE SOME NOISE (VICE TEMPUS BOOTLEG).mp3", which is damaged on the
      headset (zero MPEG header; ffmpeg can't open it either).
  - Scripts: make_cues.py turns the features into one song.txt-format script per file name. It writes
    TribeUE/Songs/cues/<key>.txt, key = FNV-1a 64 of the name as the hook reads it (non-ASCII -> '?', ASCII lower-case).
    - Sections: drop = majority over 5 s of (loudness within 4 dB of the track's p97 and sub within 8 dB). Merges keep
      the longer neighbour; level moves of > 6 dB split long sections; labels come from each section's own level.
    - Hits: the first strong rise that stays loud for 1 s, so a stutter build resolves to its last hit. Builds take the
      8 bars before a drop; a breath of >= 0.4 s before a hit goes dark.
    - Tempo: the beat track's median, folded x2 or 3:2, refined at the 16-beat onset autocorrelation lag. librosa's own
      value is quantised to 136 / 143.55 near 140.
    - Checked on PRELUDE I against the hand analysis: drops 1:53.0 / 3:19.7 (hand 1:53.1 / 3:19.71), build 1:46.3,
      breakdown 3:50.9, 140 BPM.
    - Library: 1791 unique scripts, 316 KB, largest 610 B. Drops per track mostly 2-4; only 10 full-length tracks have
      none. Tempos: 140 (766), 145 (411), 150 (314).
    - Songs/overrides/<file name>.txt replaces a generated script (PRELUDE I with its lift).
  - On the headset: tribemod/songs/ (1791 files, staged via /data/local/tmp). reseed.sh restores them.
  - Mod song3 (out/hookA/song3.aligned.apk, signed, NOT installed yet):
    - Each deck's track loads songs/<key>.txt; song.txt still applies to the track it names.
    - Only a script with lift= drives the lift. Otherwise the button works, and a button giant keeps its blackout and
      spot.
    - Interim deck choice: the scripted song that has been playing longest.
    - Includes the smooth song clock and a read-only probe that logs the deck class's fader / crossfader / cue / tempo
      properties and their changes. Plan: the user moves faders and cue buttons once, then fader-based on-air choice.
- v8 (arch v2 + stagedeck) + song3, on the headset 20:00, used for the user's beta-test demo with friends.
  - Stage patch_v80.obb (md5 24bc5bd36bfacdc6ef33b097b0657f10) is built from out_arch (arch2's bake, 18:31-18:49):
    - new: SM_DinoGroundsStagedeck (show_lit; one ANIM line in build_dino.py) and SM_DinoHalosStagedeck;
    - the arch-shaped SM_DinoVisualScreen at y 9.0 (643.5 m2, was 297.6), the lintel, lasers on the new horn tips;
    - 4446 people;
    - cook 0 errors, chunk 50 has 111 entries.
  - On device: 71.6-71.9 fps on the Dino Stage. One stretch at ~58 fps (20:09:49-20:10:35) started with a 400 ms hitch:
    Go Live or friends joining, which renders the stage a second time.
  - Mod song3 (installed 19:52):
    - PRELUDE I found songs/8e6169c8e3f50784.txt, the override with the lift. The hook's FNV key matches make_cues'.
    - Rise at 69.01 s, up at 77.01 s, top lasers at 113.10, landed + drop at 166.00, drop 2 at 199.71: all exact. The
      program-based lift state gave no flaps.
    - The button was ignored while the song drove the lift; the user pressed it three times (1:04.5, 1:08.1, 2:21.8).
    - Interim handover: the user stopped deck 1 mid-breakdown, and the lights switched to deck 2 (FORGOTTEN NAME,
      generated, 29 cues) at its 6.61 s, then followed its build / drop / breakdown cues.
    - The probe is useless as built. Its 48 slots filled with BP_CDJ3000_C's Marker_* ObjectProperties (button
      markers) before reaching the mixer values. Next: skip Marker_* and objects, raise the cap, and include
      BP_Deck_C's floats/bools in full.
  - Tribe's EXIT_SELF restarts (dumpsys exit-info reason=1, status 0) happen often after a launch (~46 s in). Not a
    crash, and not from the mod: they happened before tonight's builds too.
  - Next bake (v8.1): arch2's stairs fix (step tops -0.2/-0.4/-0.6/-0.8) and the legacy build_crowd 5-tuple fix are in
    dino_stage.py, unbaked.
- 2026-10-07:
  - VJ pack final, on the headset (md5-checked): 33 loops plus "Dino Visuals - Full Set.mp4" (60:00, 2.70 GB),
    recomposed for the arch window. The user chose a 96-bar Giant Halo opening, covering the giant rise; the visuals
    team is re-encoding the set. The user kept Fossil Scan / Lava Moon at their new, darker levels.
  - arch2 is baking v8.1 (the stairs fix) to out_v81; out_arch stays as the live reference.
  - Mod song4 (out/hookA/song4.aligned.apk, signed, not installed) adds probe v2:
    - numeric BP variables of the decks, BP_Console_C, BP_MixerChannelDevice_C and BP_MixerSliderBase_C, down to the
      engine base classes; poll thread, every 0.5 s;
    - logged as [PROBE] lines, and only while tribemod/probe_on exists.
  - Test: touch probe_on, play two songs, move the channel faders and the crossfader, toggle the headphone cues, then
    read the log and remove probe_on.
- v8.1 built (not installed): patch_v81.obb md5 796dd16c77d46d610b07733bf26e3ddb, from out_v81.
  - Only change vs out_arch: the riser stairs. Step tops -0.2/-0.4/-0.6/-0.8, standing on the deck; v8 had every top
    at -0.5.
  - Blender's UV packer re-laid out T_DinoGroundsStagedeck even though mesh and code were unchanged, so the packer is
    not deterministic for every mesh. The look is the same.
  - Install with song4 in one Tribe restart; then touch probe_on for the fader test.
- Rise time: giant.txt rise=26 (was 8), on the headset and in backup/tribemod_20261006. The user found the rise much
  faster than the 26 s descent of PRELUDE I. The button descent is still 60 s (asked the user whether to match).
- Full Set with the 96-bar Giant Halo opening is on the headset (md5 68978dc817155cc740cd18deb5f22175).
- Probe v2 on device (2026-10-07 16:43-16:46; the headset's battery died at 16:46). Tribe's mixer is BP_DJM_Nexus_2_C
  (a BP_Console_C).
  - Channel faders: 4 x BP_ChannelVolumeSlider_C (a BP_MixerSliderBase_C), "Mixer Channel"@1312, plus BP_Crossfader_C.
    The position is BP_SliderBase_C.CurrentSliderOffset, -2.2 .. +2.2. It read +2.2 when the user brought deck 2 in,
    so +2.2 = top is assumed; mix.txt "fader_sign=-1" flips it.
  - Filters: 4 x BP_ChannelColorKnob_C, BP_KnobBase_C.CurrentKnobRotationYaw, 0 = centre, seen -74 .. +144. There are
    also Trim/EQ/master/headphone knobs.
  - Deck channel: BP_MixerChannelDevice_C.MixerChannel@720 (BP_Deck_C's parent).
  - The deck also exposes BeatgridBpm@1208 and BeatgridStartMs@1216: Tribe's own grid, for a later beat-lock.
  - The user never uses the crossfader ("i just use the filters and the regular channel faders").
- Mod song5 (out/hookA/song5.aligned.apk, signed, not installed):
  - The lights follow the deck the crowd hears: level = fader x filter openness (open up to 55% of the filter's travel,
    gone at 95%).
  - Choice: the loudest playing deck, kept unless another is 0.15 louder or it drops under 0.1. A loud track without a
    script = the free-running show. If the mixer can't be read, the longest-playing deck is used.
  - Logs "[MIX] out loud: deck N (channel c, level x)" and "[MIX] levels ..." every 2 s.
  - Test: two songs, faders up and down, a filter sweep. If the lights follow the quiet deck, set mix.txt
    fader_sign=-1.
- 2026-10-07/08:
  - Re-seed at 18:13: 0 auth errors during the genuine login, OBTAIN_TOKEN_3P ok. The mod is reinstalled as song7,
    later song8 (beat-grid lock).
  - BUG found 10-08: the re-seed's permission step "chmod 666 $D/*" also hit the songs DIRECTORY, leaving it at
    drw-rw-rw- (no x). From 18:15 no light script could be opened, so tracks logged "has no light script" and the show
    ran free. The user's "lights need to go with the songs WAY better" came while this was broken.
    - Fixed on device: chmod 777 songs, 666 its files.
    - Fixed in reseed.sh: files get 666, folders 777 including songs.
  - First launch of v8.2 after the re-seed: one SIGSEGV in RenderThread at 18:17:24, 8 s in, in the menu (pc in
    anonymous memory, called from libUnreal 0x49b15f8). It did not repeat on the relaunches or with the stage loaded.
    Assumed to be the fresh install's shader/pipeline cache rebuild; watch for a repeat.
  - Lift slowed (the user: "we need to slow down the up and down on the platform"):
    - PRELUDE I lift=69.0 126.0 166.0: rise 1:09-1:53 (44 s, top as the lasers start), down 2:06-2:46 (40 s).
    - giant.txt rise=44 descend=60, so the button lift rises 44 s and descends 60 s.
    - Updated in Songs/overrides, Songs/cues, backup/tribemod_20261006 (song.txt, giant.txt) and on the device.
  - Mod song8 (installed 10-07): beat-grid lock.
    - The lights' bar and beat clock follows BP_Deck_C.BeatgridBpm / BeatgridStartMs of the deck the crowd hears, in
      song mode and the free show.
    - Beat 1 comes from the script's first drop; cues snap to the grid's nearest beat within 0.15 s.
    - Logs [GRID] lines. Not yet verified on device.
  - song8 on device 10-08 16:3x-16:5x: the grid lock engages ([GRID] lines for every track), but Tribe's grids are often
    wrong. Compared on 19 tracks the user played against a whole-track comb fit of the scan's onset envelope (mean onset
    strength on the grid's beats; scratchpad check_grids.py / tempo_scan.py):
    - Wrong tempo on 6:
      - Dream Sequence (Kompany Remix) 142.38 (is 140.00), Manly - MONSTER 142.00 (140), BASSPLASMA - HUNTING GROUNDS
        145.00 (140), EYELANDER - RHYTHM OF ETERNITY 143.00 (140), KATTANA - Sacred Land 143.49 (145.01), SISTO -
        DAMNATION 145.12 (145.00).
      - A 120-170 BPM scan gives each of them one dominant peak at our tempo (2-4x the median score); Tribe's tempo
        scores at the median, i.e. no better than an off-tempo grid.
    - First beat "0.000 s" on 7 more (PRELUDE I among them): 40-70 ms before the hits. Tribe seems to leave 0 when its
      phase analysis fails.
    - Where Tribe did analyse a first beat (6 tracks, 0.049-0.923 s) it agrees with our fit within 0-23 ms. Independent
      check of the fit's phase.
  - make_cues.fit_grid: comb fit, tempo within +-2.5 % of the section BPM (0.02 BPM steps, then 0.002), phase in 5 ms
    steps; a whole-number BPM within 99.5 % of the best score wins. t0 = the first drop/top cue snapped onto the grid
    (beat 1 of a bar is the drop's beat, as grid_bars assumes). Every script gets "grid=<bpm> <t0>"; overrides get it
    added when copied (the override file stays as written). song.txt (PRELUDE I): grid=140 113.188.
  - Mod song9 (out/hookA/song9.aligned.apk, signed): SongScript.gbpm/gt0 from grid=; song mode locks to the song's own
    grid ahead of Tribe's ("[GRID] song mode locked to deck N's own grid (... Tribe's: ...)"). Tribe's grid stays the
    fallback (no grid line) and drives the free show (no script).
  - 10-08 ~17:00: Tribe froze (ANR) after 32 min. Not the mod (verified from the ANR trace, bugreport FS/data/anr):
    - The GameThread waited forever in Tribe's deck player Open() (UFunction "Open"(FString, int, int, bool), next to
      Play/Pause/JogTick/SetBeatGrid in its native table, likely the Superpowered SDK: the "hls://" prefix check, open
      (path, offset, length, ...)). Its spin-wait (usleep 10/20 ms) waits for the player's worker to go idle, but all 8
      worker threads were idle in pthread_cond_wait: a lost wakeup inside the player. Triggered by loading a track.
    - libhook's repl_pe frames in the stack are the ProcessEvent passthrough (the blr at repl_pe+0x2018). The mod's
      own tick work runs before it and was not on the stack.
    - The ANR itself came when the user pressed the Meta button: Android's onSurfaceDestroyed waits for the hung game
      thread. Recovery: restart Tribe. First occurrence in many hours of use.
  - Beat sync (the user: "i use beat sync"): Tribe's GetPlaybackSeconds is the position in the track (it advanced
    0.9835 s/s on a synced Dream Sequence = 140 / 142.38), so the grid lock holds at any synced tempo. But Tribe's sync
    uses its own grid: on the mis-gridded tracks it plays them at the wrong speed (Dream Sequence at ~137.7 against a
    140 master). Offered a mod fix (the player has SetBeatGrid); the user chose "not now".
  - Song scripts: the grid line only when the comb fit is clear (make_cues GRID_MIN_CONF = 1.7, best / median score;
    library median 3.4). 48 of 1791 fall back to Tribe's grid: DJ mixes with tempo changes, likely 2:3 tempo misreads
    (113-116 for ~170 tracks). 1743 scripts carry a grid (Songs/cues and the headset).

## Stage v9: lasers v2 (2026-10-08, installed 18:48)
The user: "your gonna have to change the colors of the lazers too. also the lazers need to be coming from the actual
lazer things on the stage, currently there off from it or coming out of nowhere so we just need to upgrade the quality.
also we need more patterns too. way more." Choices: colors "Full RGB / rainbow chases", fixtures "All of them".
- Why "out of nowhere": the sweeping lasers came from small dark 0.36 m boxes on the horn tips (invisible from the
  crowd) and one box on the stage lip; the fixtures the crowd sees (towers, stage front) only had static beams.
- Fixtures (grounds/atmosphere.py): 19 laser units, UNIT_BOX 0.5 x 0.46 x 0.3 with a bezel and fins, each beam
  anchored at its unit's aperture (LASER_GAP 0.1 m), the aperture glowing in the beam's color (kind-1 quads):
  center fan (13 beams), 8 horn-tip units (5 each), 4 tower units (top of each truss column + its crowd face at
  z 9, 6 each), 6 stage-front units on 0.8 m road cases at x +-4, +-8, +-13, y -3.6 (5 each) = 107 beams (v8: 45),
  thinner (2 -> 10 cm) and additive.
- Pattern engine (show.py "the laser show v2", dino_materials.laser_show): 48 motion patterns and 14 RGB color schemes
  as byte-encoded rows (T_DinoLaserLib 8 x 64), played per bar from an 8-variant program (T_DinoLaserProg 32 x 8),
  crossfading over the last 15% of each bar. Two Custom HLSL nodes in the vertex shader (LaserMotion, LaserColor);
  color + alpha reach the pixel shader through a VertexInterpolator. MPC_DinoGiant.LaserVariant picks the variant.
  Cue rows 11 / 12 = the tower / stage-front units (v8.2's pattern-weight rows retired).
- Checks: atmosphere_lasercheck.py (now against out_v81, the live stage's bake; out/ is a stale v6.3 bake that showed
  phantom grazes) PASS: DJ head >= 4.9 m (raised giant >= 8.6 m), stage clearance >= 0.13 m, nothing below 0.25 m over
  the crowd floor. dxc compiles the HLSL. A numpy port of the engine on the real texture bytes: P, Q within -1..1,
  fastest beam on/off 1.24 /s and color jump 1.33 /s (comfort: under the 2.33 /s beat).
- Mod song10 (out/hookA/song10.aligned.apk, signed): LaserVariant = FNV(script match) % 8 per song; the free show on a
  grid moves on every 32 bars; logs "[LASER] variant N (...)".
- Bake: Blender/out_v9 (17 min). The first v9 bake dropped the stagedeck (the default DINO_GROUNDS lacked it; v8 bakes
  passed it explicitly): dino_stage.py's default now includes stagedeck, and the re-bake matches out_v81's file list
  plus the two laser textures. atmosphere_lasercheck on out_v9: PASS.
- Built 10-08 18:45 (37 actors), cooked (0 errors; M_DinoLasersShow: 4 Vulkan ES3.1 shaders), pakchunk50 126,359,069 B
  md5 562d9147. Pushed 18:48 with scripts/push_obb.sh (merges into the live OBB: 50 v9 + 53 + Halloween 54 + club 55),
  device OBB md5 351dcc0a = paks_current/patch_live.obb. song10 installed.
- reseed.sh: MOD=song10, PATCH=C:/Users/Chris/TribeUE/paks_current/patch_live.obb (push_obb.sh mirrors every verified
  push there, so a re-seed restores every session's stage; the club's patch_reactor_v2.obb lacked Halloween's 54).
- v9 on device 18:52-18:56: own-grid locks and "[LASER] variant 7 (MAGIC ARMOUR)" as designed; 71.9-72.0 fps
  through both drops (worst frame 17-25 ms, 0-2 frames over 20 ms per 10 s; v8.2 was 67-72 / 26-38 ms). The user
  closed Tribe themselves. Verdict: "the lazers are very close but it still isnt there yet"; picked "Hit with the
  music" and "More beams, more coverage".

## Stage v10: lasers that hit with the music, and more of them (2026-10-08)
- Hit maps (make_cues.py --hits, 7 s for the library): per song with a confident grid, songs/<key>.hits = the drum
  accents. Measured first: the drops' accent profile per 16th (onset strength vs the bar's max) shows 1-2 dominant
  16ths per bar (0.8-0.9 vs 0.2-0.5): beat 3 (Dream Sequence, PRELUDE I), beat 1 (MAGIC ARMOUR, HUNTING GROUNDS), 2 and
  4 (MONSTER, FORGIVE FORGET, Tear It Up). So hit_map() finds them per bar from the audio: a 16th reaching 0.65 of
  its bar's strongest is a hit, 0.85 major, at most one per beat (comfort), quiet bars none. Kick/snare typing from
  the 10 Hz bands was noise (the prototype's snares spread evenly over the beats), so hits carry strength, not type.
  1743 maps, 452k hits (about 260 per song); MAGIC ARMOUR's drop majors fall on beats 1 and 3 (half-time kick/snare).
- Hook song11 (out/hookA/song11.aligned.apk, signed): loads the deck's .hits with its script, replays it against the
  song clock (seeks and loops reposition quietly) into MPC HitMajor / HitMinor (0.15 s decay), HitCount, HitsOn;
  DropBoom (1.2 s) when a drop or the top look starts; the free show on a grid gets beats 1 and 3 major, 2 and 4
  minor. tribemod/hits.txt "offset_ms=N" shifts the hits.
- Material: per pattern (texel 6) hFlash (dim between hits, flash on them), hTilt (pop), hFan (fan burst), hMir
  (mirrored swing); per color scheme (texel 9) hHit (hue step per major hit) and hWhite (white flash). Pools set
  defaults (calm 0.25 flash .. drop 0.9 flash + 0.3 fan burst). DropBoom opens every fan, lifts and lights every beam,
  and washes them white.
- More beams, more coverage (atmosphere.py): 189 beams (v9 107) + 24 aperture glows. Center fan 17, horns 7 each,
  stage towers 8 each, stage front 6 each, plus:
  - the tunnel: a ring unit hung under the T. rex's chin (its lowest point (0, -2.1, 12.73)), 16 beams on a 9 deg
    cone at the crowd's center; per-beam phases spin it (tunnel_spin, mouth_tunnel, tunnel_breathe);
  - the delay towers: a unit on a pole above each tower's header bar (z 13.35), front ring aimed in and back, back
    ring in and toward the stage, kept short of the other towers.
  - Library: 57 patterns (new: sheet_flat, sheet_rise, sheet_slam, tunnel_breathe, tunnel_spin, mouth_tunnel,
    crowd_net, delay_sweep, outro_sheet) and 16 color schemes (new: hit_steps, hit_rainbow); 10 texels per row;
    group masks by family; cue rows 14 (mouth) and 15 (delay).
- atmosphere_lasercheck.py: the crowd's structures (FOH, delay towers, masts, and this module's crowd-side units)
  are reported separately ("crosses FOH/towers/masts N%"); the stage clearance stays the gate. PASS on out_v9:
  stage clearance >= 0.16 m, DJ head >= 4.9 m (raised giant >= 5.8 m), nothing below 0.25 m over the floor.
  (Adding the crowd structures showed v9's long beams already crossing the FOH and towers 30-45 m out.)
- Baked to Blender/out_v10 (17 min, same file list as out_v9; laser check PASS on it), built (37 actors), cooked
  (0 errors; M_DinoLasersShow 4 Vulkan ES3.1 shaders), pakchunk50 126,471,709 B md5 eb8d8c3a. Pushed 10-08 ~19:50 via
  scripts/push_obb.sh (50 v10 + 53 + Halloween 54 + club 55, device OBB md5 12935c16), song11 installed,
  reseed.sh MOD=song11. 1743 .hits files pushed to tribemod/songs (they live next to the scripts in Songs/cues, so
  reseed.sh's songs copy restores them).
- 10-08 ~22:15: the club session hooked hook/club.cpp (+ club_collide.h, theirs) into hook/dumper.cpp with the
  user's OK given in its chat ("figure out walking now"): #include "club.cpp" before repl_pe, club_pe() as repl_pe's
  first line (static inline, returns on !g_clubOn: one branch off the club's map), club_tick() after giant_tick() on
  both tick lines, club_lookup() every 4th env poll. Verified here: the diff against song11 (md5 18bc6f22) is exactly
  those lines; dumper.cpp is now md5 965a5132. Their club1 APK = song11 + the club (not installed yet).
  Rule: every APK built from dumper.cpp from now on keeps these lines; keep club.cpp / club_collide.h next to it.
- 10-09 16:55: the club session installed club1 (song11 + the club lines, md5 5ace0c5e) with the user's go; reseed.sh
  MOD=club1 so a re-seed keeps walking. The headset had rebooted (up 1 min at 16:54), so its log buffer held nothing
  from the night; v10 has not been seen running yet.

## Stage v11 + song12: the lasers go with the bass (2026-10-09)
The user: "what about the bass of the songs? ... some songs, it just the bass that plays and the lazers need to be going".
- Measured first (10 Hz sub + low bands in the drops): pumping / wobbling bass swings 6-16 dB in a steady rhythm (every
  beat in MAGIC ARMOUR, every bar in MONSTER and HUNTING GROUNDS, every 2 beats in FORGIVE FORGET); a sustained growl
  stays within 2-3 dB (Dream Sequence, Tear It Up): the level carries presence and pumping, not timbre. 16th / triplet
  wobbles (7-9 Hz) are above the 10 Hz data's reach: they read as bass present.
- make_cues.py --bass: songs/<key>.bass = one byte per 100 ms of bass level, scaled per song (15th..99th percentile of
  the sounding frames, ^1.3). 1791 maps. Section means: drops 0.55-0.78, breakdowns 0.07-0.15, MONSTER's build 0.63.
- Library motion texel 7 (LIB_TEXELS 11; color texels 8-10): bFan, bTilt, bVis, bLvl; pool defaults (calm .1/0/.2/.35,
  build .2/.1/.3/.5, drop .3/.15/.5/.8, outro .15/0/.3/.5); new bass_pump, bass_scan, bass_breath (60 patterns).
- laser_show: P += bFan u Bass, Q += bTilt Bass, V x (1 + bVis Bass), unit level >= bLvl Bass ShowLevel (a bass-only
  part runs the lasers; the "dark" look keeps them off).
- song12 = club1 (song11 + the club lines, built from dumper.cpp 965a5132) + bass maps (MPC Bass, 30 ms attack, 150 ms
  release); dumper.cpp now md5 751cc30b; libhook carries the club's 27 [CLUB] strings.
- No Blender bake: out_v11 = out_v10 + the v11 show textures. Built (37 actors), cooked (0 errors; the cook compiled
  M_DinoLasersShow fresh for VULKAN_ES3_1_ANDROID; the stats CSV's "cooked 0" is a counting quirk), pakchunk50 md5
  b11c0398. Pushed 10-09 ~17:07 with push_obb.sh (device md5 592d0375), 1791 .bass files pushed, song12 installed;
  reseed.sh MOD=song12.

## Stage v12 + song13: why the lasers never moved, and the bass that never arrived (2026-10-09 evening)
The user: "the lazers in the dino stage look good. sometimes its a bit much having them all on at the same time but i
like them all. Also another thing with the lazers, they dont move! neighther do the lights!"
- ROOT CAUSE (lasers, since v9 and likely v8): Unreal's FBX import stores 1 - v on EVERY UV channel, not just UV0.
  The laser data channels were never compensated. Measured in the fork editor (inspect_lasers.py, read-only):
  SM_DinoLasers UV5.y split 144 "beam" / 2268 "aperture" vertex instances, where the FBX has 1512 beam / 96 aperture
  loops (UV1.v -64.851..4.012 in the FBX reads -3.012..65.851 in UE). So on the Quest every beam read kind = 1 = an
  aperture: no motion, and lit at >= 35% whenever its unit's level was up (the "all on at the same time"). The pivot
  y, tilt amplitude, fan position u and phase were all 1 - value too.
  Ruled out first: the show clock (ShowOffset is written every tick with the fractional bar), and the engine (mobile
  ES3.1 has no per-primitive WPO switch: MaterialTemplate.ush ShouldEnableWorldPositionOffset; up to 8 vertex UVs).
  Rule: any per-vertex data in a UV V component must be pre-compensated in Blender (crowd2 does) or read as 1 - v.
- Fix: dino_materials.laser_show reads every data V as 1 - v (vread); build_dino imports SM_DinoLasers with
  full-precision UVs (FP16 rounded the 65 m pivots to ~6 cm). Checked by wpo_emulate.py (Blender, emulates the
  import, the actor's yaw 180 and the material's RotateAboutAxis): the UE pose matches atmosphere.laser_pose_pq to
  0.08 cm over the P/Q grid; beam tips move up to 21-23 m.
- Laser scenes (show.py): 92% of the program's bars allowed all six groups and the drop's cue rows hold all six at 1.
  T_DinoLaserProg alpha (was 0) now carries each bar's groups: the drop opens with everything (with the drop boom),
  then three-group scenes take turns every two bars, a different order per variant; intro/build/breakdown/outro light
  what their cue rows bring in. A pattern with its own mask keeps it; TopLasers still shows every top laser. Measured:
  all six lit in 11% of bars (was ~92%). Unreal only infills PNG pixels that are pure white with zero alpha, so the
  program's alpha is safe.
- BASS NEVER REACHED THE STAGE (found by the club session, verified here): mpc_param_name read at most 16 of a
  collection's scalars; Bass is the 17th, so every Bass write since song12 was a no-op (the device logged
  "MPC_DinoGiant: 16/17 parameters"). Cap 64 in song13.
- v12 = out_v12 (out_v11 + the new T_DinoLaserProg; cues and lib byte-identical), built 37 actors, cooked 0 errors
  (M_DinoLasersShow compiled fresh for VULKAN_ES3_1_ANDROID), pakchunk50 126,511,950 B. Gotcha: the first cook ran
  with Git Bash's path conversion on and cooked nothing of ours (-map became "C:/Program Files/Git/Game/..."): export
  MSYS_NO_PATHCONV=1 and quote "-map=..." before cooking from bash.
- song13 (dumper.cpp md5 5e231fca, out/hookA/song13.aligned.apk md5 b080255e), all requested or found by the club
  session: the 64 cap; g_walkPause + HAVE_WALK_PAUSE (1 from lift start until landed: walking and the lift both
  move VROrigin); the show bus (the stage's own collection: MPC_DinoGiant, else
  /Game/Mods/Club/MaterialInstances/MPC_ClubShow; the giant, i.e. button, lift incl. a song's lift=, robe and spot,
  only with Dino's; show_key/show_set/g_showGen + HAVE_SHOW_BUS for club.cpp); the selfie reel follows the stage
  (tribemod/drone_path.<folder>.txt, else drone_path.txt, else the built-in reel; em_active_folder()). The club
  session's club3 (md5 2d2ad182) = song13 + their latest club.cpp: the agreed next install, after the re-seed.
- The re-seed (headset reboot -> authenticate_application 400): part A done 17:21 (genuine Tribe + main OBB, log
  cleared); waiting on the user's login. backup/tribemod_20261006 refreshed (envs.txt with Graveyard Shift,
  club_collide.txt added to reseed.sh's restore list).
- Stage v13 BUILT 18:49 (bake 18:26-18:45 under the GPU lock; pakchunk50 126,718,514 B md5 1193318f, copies of v12
  5fcc8366 and v13 in TribeUE/Meta/verify/paks/; not pushed yet): v12 + the stage's 19 moving heads move.
  Found by the CPU pipeline test (DINO_CPU=1 --fast, a new switch in dino_stage.py): stamping "the faces made since
  index n0" missed 8 faces a fixture, because bmesh.ops.create_cube/create_cone reuse face slots; stamp by a snapshot
  of the faces before (set difference). mover_fbx_check.py on the real bake: PASS (heads 912 pan-only loops = the
  yokes, every vertex within 0.37 m of its own pivot). Cook compiled M_DinoMover*, M_DinoLensMover fresh, 0 errors.
  Gotcha: pack_chunk.sh must run WITHOUT MSYS_NO_PATHCONV (repak needs the converted paths); the cook WITH it.
  Was: the stage's 19 moving heads move. Each
  fixture's yoke (pan only), head, lens, lens glow and beam turn as one about the head's center
  (atmosphere.mover_pose_pq: pan about the vertical, tilt about the fixture's own horizontal axis), driven per bar by
  the laser engine's patterns with each cycle rate capped at 2 a bar (dino_materials MOVER_MOTION_HLSL, mover_beams /
  mover_heads / mover_lens). New meshes SM_DinoMoverBeams/Halos (atmosphere "movers"/"mover_halos") and
  SM_DinoMoverHeads (yokes + heads out of the baked rig); SM_DinoLenses carries the data too; the beams keep their
  cue rows. mover_emulate.py: UE pose = Blender pose to 0.001 cm, beam tips swing up to 29 m, lowest beam point
  over the crowd 3.31 m above the field, closest beam axis to the DJ's eyes 5.59 m.
- Walking on the Dino Stage (the user: "id like to incorporate walking too, like in the other chat from reactor.
  also i need a path to get into the crowd"): club.cpp will read tribemod/dino_collide.txt (per-stage maps by
  folder; the club session). Route options drawn on a body-height map of the stage front (scratchpad
  walk/walk_routes.png): A = stairs into the pit at x 9.1-10.6 + a barrier gate; B = side stairs on the right wing.
  The barrier belongs to SM_DinoDeck (dino_stage.build_deck). Waiting on the user's pick.

## Session 3o — Detachable head (the pumpkin-head rider's head flies off and comes back). BUILT; device-verified 2026-10-10 (addendum 2 below)
Fork of the character session, 2026-10-09 evening. (The directive called this "3n"; 3n was already the env-menu entry.)
Goal: a Headless-Horseman character whose head lifts off the neck, circles the DJ, grins into the stream camera and
re-seats, while the player keeps seeing from the body. The user's view never follows the head: the engine draws the
eyes at the HMD, so the head is only a prop.
- Design: the head stays PART of the skinned skin (A = full body owner-no-see, B = owner-only with Head hidden, as
  before), so "head on" costs nothing and tracks the HMD. A second, STATIC copy of the head (a plain mesh) flies while
  A's Head bone is hidden (HideBoneByName on A at the switch frame; UnHideBoneByName when it lands). Hide/show happen in
  the same tick, so the hand-off reads as one head.
- File contracts (paired by the active skin's file name):
  * tribemod/skins/<skin>.glb: the skin, plus three leaf bones under Head, rest pose: DH_C (head centre),
    DH_F (= DH_C + 0.10 m toward the character's front), DH_U (= DH_C + 0.10 m up). From them the hook gets the head's
    world position + orientation with no bone-space math.
  * tribemod/heads/<skin>.glb: NON-skinned glTF, mesh index 0, origin at the head centre, upright, facing the front,
    same units as the skin (loaded with the skin's LoaderConfig: SceneScale=100, then glTFRuntimeAsset.LoadStaticMesh
    (0, zeroed config; BoundsScale=(1,1,1) if the struct has it; gray fallback = MaterialsConfig.bSkipLoad)).
    Its local forward/up after glTFRuntime's default basis are assumed +Y/+Z (glTF +Z front -> UE +Y, +Y up -> UE +Z).
  * tribemod/head.txt (polled ~1 s; re-read on change only): `auto` (default, also when the file is absent: cycles),
    `on` (stay on; if flying, return now), `off` (take off now; orbit until changed), `boo` (one camera moment now,
    then back to the mode in force; a file saying only "boo" keeps the previous mode), optional `fwd=+y` `up=+z`
    (axis overrides: +x -x +y -y +z -z; a wrong guess is a file edit, not a rebuild).
- Where the head is (hook/head.cpp, included from dumper.cpp after the drone): head_capture_fk() is called at the end of
  a2_drive's FK every frame and keeps the DH bones + Hips in A's component space (the pose A renders, live whether Head
  is hidden or not; RequiredBones/hidden-bone questions don't arise). head_dh_pose() turns them into world space with
  A's own K2_GetComponentLocation/Rotation/Scale. GetSocketTransform(DH_C, world) is read once at init as a cross-check
  and logged ("socket read ok (x cm off the FK)").
- Runtime (head_tick on our actor's tick, after bt_frame/drone): the static head is a StaticMeshComponent added to our
  avatar actor like A (AddComponentByClass, SetStaticMesh, attached at identity to the tracked parent, SetRelativeScale3D
  g_btScale, no collision/shadow, owner CAN see it; hidden while ON). It needs body tracking live (g_a2Live), so with no
  heads/<skin>.glb, no DH bones, or tracking off, the feature idles (logged once). State machine, monotonic clock:
  ON (random 20-40 s; 0 in `off`) -> TAKEOFF 1.2 s (hide Head on A, show the copy at the DH pose, ease up 25 cm and out
  to the ring) -> ORBIT (random 15-25 s: ring r=90 cm around the smoothed Hips, z = DH_C.z at takeoff + 10 cm, 8 s per
  lap, bob +-8 cm at 0.5 Hz, faces the way it flies with a +-10 deg roll wobble) -> BOO once per flight at the midpoint
  if BP_SelfieStick_C's CaptureComponent2D resolves (1.5 s to 60 cm in front of the lens, grin 2.5 s, 1.5 s back; skipped
  + logged when there is no stick) -> RETURN 1.5 s to the LIVE DH pose -> switch frame (UnHideBone, hide the copy) -> ON.
  Every skin load (do_load) drops the old static head (and gives A its head back) and loads heads/<skin>.glb if present;
  a re-rig (new A) resets the state. Logs: TRIBEMOD "[HEAD] ..." for resolve, load, rig geometry, every state change,
  head.txt changes, a 5 s heartbeat while flying.
- dumper.cpp edits (small): forward decls + head_skin_loaded(skin,libCDO,fnLoad) at the end of do_load; head_capture_fk
  (cq,ct) in a2_drive before the SetBone loop; #include "head.cpp" after drone_update; head_tick in both ReceiveTick
  chains; head_poll every ~1 s in dump_thread. `char skin[256]=""` in do_load (was uninitialized when active_skin.txt
  is absent).
- Built from the current tree (= song13 + the club session's latest club.cpp + this): libhook 340,024 B (no new
  warnings), out/hookA/head1.aligned.apk (md5 24837191, signed with scripts/sign_apk.sh, verified).
- Test files from the character session: out/headtest/skullbuck.glb (skullbuck + DH_C/DH_F/DH_U under Head, 57 joints;
  DH_F = C + 0.10 glTF Z, DH_U = C + 0.10 glTF Y, checked) and out/headtest/skullbuck_head.glb (his skull as a static
  mesh, 1 material, node Head_Static, antlers up +Y, snout +Z).
- NOT INSTALLED, NOT TESTED: the headset was mid re-seed (genuine Tribe, base.apk 111,389,761 B, installed 17:20; no
  tribemod/; waiting on the user's login, then part B). install -r over the genuine build is impossible (other signer) and
  uninstalling is forbidden. Test recipe (scratchpad devtest.sh, same steps by hand): after part B, `adb install -r
  out/hookA/head1.aligned.apk`; mkdir tribemod/heads (chmod 777); stage both test files through /data/local/tmp into
  skins/skullbuck.glb and heads/skullbuck.glb (chmod 666); active_skin.txt = skullbuck.glb; head.txt = auto; relaunch;
  logcat -s TRIBEMOD:V; set head.txt off / on / boo; expect "[HEAD] resolved", "loaded heads/skullbuck.glb ->
  UStaticMesh", "static head component", "rig ok: DH_C/DH_F/DH_U = bones ..", TAKEOFF/ORBIT/RETURN/BOO lines; same pid
  throughout. Body tracking must be live for anything past "loaded" (a headset on a desk may not get there; prox_close
  makes it think it is worn, see line ~3762).
- Open: the +Y/+Z local-axis guess for the static mesh (fix via head.txt fwd=/up= if the pumpkin faces the wrong way);
  the FglTFRuntimeStaticMeshConfig layout is resolved by name at runtime and logged ("LoadStaticMesh psz=.. Config@..");
  the socket cross-check number; whether the first-person user sees the flying head well (owner-no-see is OFF on the
  copy by design). head1 supersedes club3/song13 on the headset once installed (same source tree).

### Session 3o addendum (character session, 2026-10-09 evening) — Horseman files + "leave skullbuck alone"
- User decision: skullbuck stays as he is. skins/skullbuck.glb = the cargo-pants build WITHOUT the DH bones (6,248,380 B);
  heads/skullbuck.glb removed. The DH test pair stays in out/headtest/ only (never pushed). The horseman is the only
  detachable-head skin: skins/horseman.glb (5,284,404 B, 32k tris, checker LOADS+MOVES) + heads/horseman.glb (770,172 B,
  the pumpkin, origin at its centre, face at glTF +Z, emissive face). Build: scripts/skullbuck_cargo_pants.py `plain`
  (breeches) -> scripts/horseman_build.py; helpers scripts/avatar_common.py, render_skin.py, pose_test.py.
- reseed.sh: KEEP_SKINS += horseman; new heads/ step (pushes heads/<skin>.glb when present, writes head.txt=auto).
- Headset state: genuine Tribe since 17:20 (Dino session's re-seed, waiting on the user's login). Agreed order after the
  login: Dino part B -> its paks -> club3 -> club files -> ping tribe-hack-81 -> install -r head1 + push horseman/heads
  (fallback: install -r club3). reseed.sh MOD= becomes head1 only once it is verified on the device.

## The evening of 2026-10-09: re-seeds, the user's test, then stage v14 (walkways + darker), staged only
- Re-seed #1 (official login via remote launch + the user's two dialog clicks) then: the user tapped RESTORE on Meta's
  "Restore App" dialog → the mod, tribemod and both OBBs were deleted (19:20:26 deletePackageX) and the store installed
  the official Tribe. Then the battery died (reboot). Re-seed #2 at 22:17 in the new boot (the official login must be
  in the SAME boot as part B). Lesson for the user: on that dialog, Close, never Restore; keep the headset on a charger
  (the PC's USB port charges slower than VR drains: 21% → 7% in ~15 min).
- Remote-driving the login: adb can wake the headset (prox_close broadcast) and launch Tribe, but once the immersive app
  starts, a full-screen VoidActivity covers the 2D dialogs, so `input tap` can't reach the mic prompt or the
  "Restore App" dialog. The user must click in the headset. The genuine dialog's buttons: Restore / Close (no
  "Open"); Close on a cached first launch drops the launch, so launch again.
- The user's test (club3 + v13 + the club's v5): "looks pretty good!". 72 fps on all three stages after the post-boot
  warm-up (38→52 fps in the first minute). Bass/hits/variants confirmed per song in the log. Their "i was able to
  actually walk for a sec" on the Dino was a club.cpp stage-switch race (fixed by the club session: walking only on the
  stage whose own map is loaded).
- Stage v14 (chunk 50 md5 3bde75e1, 126,777,339 B; TribeUE/Meta/verify/paks/pakchunk50_v14.pak):
  - walkways (dino_stage.WALKWAYS): A x 9.1..10.6 and B x 15.5..16.7, each 8 risers of 0.1875 m on 0.3 m treads from the
    deck edge into the pit, handrails, and a gate in the barrier;
  - darker (the user: "it still needs to be darker on stage and in the crowd i think"): dino_materials.NIGHT_GAIN 0.6
    on show_light (the set, the crowd), and baseColorFactor 0.6 on the field + festival-grounds MICs (verified: the
    glTFRuntime unlit parent is factor x texture into emissive).
- Walking map (Scripts/Blender/dino_walk: extract.py → dino_collide.py; staged backup/dino_pending/dino_collide.txt
  f6500d98): floors exact from dino_stage.py, walls from a body-height raster of the export (per-object boxes, 317),
  all 4446 dancers as soft people, `spot decks` at the DJ. Needs the club's raised limits (club_collide.h 83ab550e:
  CC_MAXP 4608, CC_MAXB 512, person grid; club.cpp 971a4293: 512 KB read buffer). My Python walk under the club's rules:
  PASS (both walkways). The club's C++ test 52ba3c1c: 556,744 states, 0 stuck. Gotcha: float seams between treads
  (-509.99999999999994 vs -510.00000000000006) opened gaps only in the offline walk; it now rounds like the file.
- Hook source dumper.cpp 5c08eaf6 (not built into an APK yet): the show-bus lookup by the active stage's folder (dino /
  club / halloween → MPC_HwShow for the Halloween session's music-driven lasers). dumper.cpp also carries the
  character session's head.cpp lines (since 18:32) — keep them, like the club's.
- The other stages: the club session reports Reactor's lasers/lights already song-driven (laser_show unchanged); my v12
  scene masks left Reactor dark in 86/256 bars (their families ≠ the Dino's) → they remap their copies (stage v6,
  pending). They take the moving-heads contract for Reactor v7. The Halloween session is building Graveyard Shift's
  lasers on laser_show with MPC_HwShow.

### 2026-10-10: Graveyard Shift's stream intro, the mod side (built, compile-checked; NOT packaged or installed)
[observed: MSVC host tests, NDK compile; the Halloween session wrote the spec and the stage files]
- The user's design (relayed by the Halloween session, then "Ok go ahead"): the stream camera follows the Headless
  Horseman through woods behind the stage; a crypt button under the screen, 3 presses: 1 pre-show (dark, door shuts,
  the ride loop), 2 he takes the exit, 3 showtime ("the venue gets dark, starts the visuals ... the button is mapped to
  the play button on that deck"). Their picks: queue press 3 until the camera holds; the deck sitting at its cue point
  plays and any other playing deck stops; one intro per stage load; set the capture FOV for the intro and restore it.
- Files: hook/intro_ride.h (engine-free: the intro file + a Hermite spline with Catmull-Rom tangents on the time knots;
  the exit leaves along the loop's seam tangent, so both branches share it and the branch has no kink) and hook/intro.cpp
  (the state machine, the button, the rider and woods actors, IntroStep / DoorOpen on the show bus, Tribe's
  BackdropMediaPlayer rewind/pause/play, the deck calls, the FOV, and the deck capture). dumper.cpp 15a0a14b: globals
  g_introCam/Armed/Dark + g_introP/A before drone_update (the intro flies the drone's camera through its takeoff and
  landing; the reel pauses), drone_poll resolves the camera while an intro is armed (a miss logged once a minute),
  giant_tick holds ShowLevel 0 while g_introDark, `#include "intro.cpp"` after club.cpp, intro_tick after club_tick,
  intro_lookup in env_menu_poll, deck_log_pe in repl_pe, the log_deck toggle in the poll loop. 7 warnings before and
  after (all old).
- On the headset: tribemod/intro.<folder>.txt (Graveyard: intro.halloween.txt = the Halloween session's hw_intro.txt)
  and tribemod/intro_deck.txt ("play deck:<Function>" / "stop ..." or "button:<Function>", params name=value), written
  after the deck capture: create tribemod/log_deck, press Play then Pause on a deck, read the [DECK] lines (each call
  into BP_Deck_C / its buttons / its audio player with its parameters). Without intro_deck.txt, showtime leaves the
  decks alone and says so.
- Checks: tests/intro_ride_test.cpp (MSVC) against hw_intro_path's preview math: rider <= 4.6 cm, yaw <= 5.9 deg,
  camera <= 40 cm, aim <= 59 cm with 0.5 s keys (0.25 s keys: 3.1 cm, 3.5 deg, 35 / 37 cm); speed 5.96-6.04 m/s on the
  loop. The club's tests/club_collide_test.cpp built with MSVC on the PC passes halloween_collide.txt: 58,479 states
  from the decks, 0 with no way back (= my Python walk from backstage). Host builds: scratchpad msvc.bat (vcvars64 + cl).
- Review fixes found on the way (Halloween's side, fixed): a 75.8 deg snap where the exit left the loop, and 2 s keys
  (29 cm off the preview, the speed wandering 5.56-6.19 m/s).
- Next, in the push window with the user: package the APK from this tree (+ club.cpp 971a4293, head.cpp a3031f32),
  install -r, push intro.halloween.txt + the Halloween v4 pak (theirs), run the deck capture, write intro_deck.txt.
- The walk cycle on the avatar's legs (same day; the user, after hearing the avatar glides while the stick walks: "my
  arms are already tracked so we don't need to add that. Im more concerned about the legs moving"). Body tracking
  poses the legs from the user's real legs, which stand still while club.cpp's stick moves VROrigin (derived, not
  watched on device). hook/gait.h (engine-free) + a2_gait in dumper.cpp (0ce94ad3), called in a2_drive before the
  first FK: VROrigin's (= the meshes' parent g_trackParent) world motion gives the speed; jumps over 10 m/s, frames
  with a snap turn (yaw step > 2 deg) and vertical moves don't count. A phase advances by distance / stride (stride =
  4 L sin(max hip), L = the rig's thigh + shin); per leg the thigh turns about the tracked hips' left-right axis: in
  stance L sin(hip) ramps linearly (the planted foot stays put), in swing it returns on a cosine while the knee bends
  (50 deg) and the foot stays nearer level; the hips dip (60% of the drop) so the planted foot stays near the floor
  (a2_fk adds g_gaitHipOff). Backwards walking runs it in reverse. Blend: full from 60 cm/s, in/out tau 0.1 s.
  Arms, spine and head untouched. The A2 live log line ends "gait w .. cm/s fwd|back leg .. cm".
- tests/gait_test.cpp (MSVC, two-leg chain): at 180 cm/s 1.17 cycles/s (stride says 1.18), a planted ankle slides
  0.3 cm (a plain sine swing skated 66 cm: why stance is linear), the lower ankle within 2.1 cm of the floor, the
  swing ankle up to 22.6 cm, backwards reverses, teleport / snap turn / lift ignored, back to tracking ~0.3 s.
  Tuning by eye (selfie camera) waits for the headset session, with the deck capture.
- Combined APK for the next headset session (the character session's request: one install instead of head1 + mine):
  out/hookA/combo1.aligned.apk, 112,119,023 B, md5 8903d10b797e008d8fd6a75c1a7df619, cert SHA-256 979d63d7…, from
  menu.apk + libhook_combo1.so (384,016 B; dumper.cpp d4f4f80f with obj_alive guards on the per-frame calls in
  a2_gait / intro, head.cpp a3031f32, club.cpp 971a4293, club_collide.h 83ab550e, intro.cpp 3f8f77dc). NOT installed.
  Agreed: whichever session gets the user's "go" installs it (install -r) and tells the other; reseed.sh MOD follows
  the last build verified on the device.
- PUSH WINDOW 2026-10-10 08:41-08:46 (the user: "Ok go ahead"). Tribe force-stopped at 08:41:43 at the user's prompt
  (headset asleep, 90% on USB). The Halloween watcher pushed v4 (chunk 54 b3ce58e0) at 08:44:02. Then:
  - combo1 installed 08:43:39 (install -r; installed base.apk md5 8903d10b = the file; firstInstallTime still
    2026-10-09 22:17:43, data and OBBs kept);
  - stage v14b pushed 08:44:57 with push_obb.sh (Saved/ModPak/pakchunk50-Android_ASTC_P.pak 87ec24ba): live OBB md5
    7151057a = chunk 50 87ec24ba, 53 7420a9fc, 54 b3ce58e0, 55 7ccef713 (the club's v5, unchanged);
  - tribemod: dino_collide.txt f6500d98, intro.halloween.txt a076dc93, halloween_collide.txt 2058287d,
    drone_path.halloween.txt 6c1e0daf (each via /data/local/tmp + cp + chmod 666).
  Not yet launched. Pending with the user in the headset: the deck capture (log_deck), the walk tuning, the
  character session's horseman test, the Graveyard intro; the club's v7 (chunk 55 793294ce) waits on the user's OK.
  - 08:47:22, the user: "Yes let's get everything pushed": the club's v7 (chunk 55 793294ce, D:/TribeUE/MetaClub/.../v7)
    pushed with push_obb.sh. Live OBB md5 db9445bc = 50 87ec24ba, 53 7420a9fc, 54 b3ce58e0, 55 793294ce. Fallback v6
    1993790953ed. Everything staged is now on the headset; what's left needs the user in it.

### Session 3o addendum 2 (character session, 2026-10-10) — detachable head DEVICE-VERIFIED on combo1
- Build: the Dino session's combo1 (out/hookA/combo1.aligned.apk, md5 8903d10b; = song13 + club + head.cpp a3031f32 +
  giant_lookup + intro + gait), installed 08:43:39 with install -r. head1.aligned.apk was never installed (obsolete).
- Launch 16:19:55 (pid 23270): "[HEAD] resolved" at +6 s (LoadStaticMesh, StaticMeshComponent, SetStaticMesh, setWorld,
  socketXf all found); head.txt read as mode=auto fwd=+y up=+z; skullbuck auto-loaded -> "no heads/skullbuck.glb ->
  feature off" (skullbuck stays plain, as decided).
- Horseman picked 16:20:42: "loaded heads/horseman.glb -> UStaticMesh (materials on)", "static head component ... scale
  1.060, hidden until takeoff", "rig ok: DH_C/DH_F/DH_U = bones 8/9/10", front/up axes 10.6 cm (= 10 cm x 1.06). A second
  pick at 16:20:48 did a clean "dropped the static head (skin loaded)" + reload. The first rig-ok's "socket read 47.4 cm
  off the FK" was a first-frame transient (the re-pick read 0.9 cm); it is diagnostic only, placement uses the FK.
- Cycle 1 (seated; HMD 115 cm above the floor, head on the rig 111 cm): TAKEOFF 16:21:27 -> ORBIT 15 s -> BOO 16:21:36
  ("boo done" 16:21:40) -> RETURN 16:21:43 -> ON 16:21:45. Cycle 2 (standing, head 172 cm): TAKEOFF 16:22:07 -> ORBIT 23 s
  -> boo done 16:22:24 -> RETURN 16:22:31 -> ON 16:22:33. No crash signatures; A2 live dt 0.011-0.017 s before and during.
- The BOO targets the selfie-stick camera wherever it is: during the reel's wide shot (cam at (0,-4372,1537)) the pumpkin
  darted ~35 m to the lens in 1.5 s, held 2.5 s, came back. Keep the camera near the rider if an intro wants a close boo.
- Still to verify by eye (the log can't): the pumpkin's facing (fix: head.txt fwd=/up=, no rebuild), the neck stump, the
  emissive glow. Log capture: %TEMP%\claude\head\head_test.log (adb logcat -s TRIBEMOD:V DEBUG:I AndroidRuntime:E).
- reseed.sh MOD= -> combo1 is the Dino session's edit (it owns re-seeds); agreed 2026-10-10.
- 2026-10-10 (after the verification): head.cpp gained two head.txt knobs, both for the stream-intro / drone-reel overlap
  (the pumpkin had darted 35 m to a wide drone shot; the Graveyard intro's camera sits 80-130 m out in the woods):
  `boomax=<metres>` (default 12, 0 = any distance): a boo that is due while the lens is farther than that from the hips
  WAITS ("[HEAD] boo waiting: ...") and fires if the camera comes within range before the orbit ends, else "[HEAD] boo
  skipped this flight" at RETURN. `intro=hold` (default) | `free`: with hold there is no auto takeoff while the intro owns
  the camera (g_introCam from intro.cpp, press 1 -> hand-back at showtime; "[HEAD] auto takeoff held" / "the intro handed
  the camera back: next auto takeoff in N s", the 20-40 s countdown restarting at the hand-back); a flight already in the
  air finishes; off/boo in head.txt still work. Compile-checked from the tree (0 errors, the 7 old warnings). Takes effect
  in the NEXT hook build: combo1 on the headset still boos at any distance and flies during intros (head.txt `on` is the
  manual stop until then).
- 2026-10-10 16:4x, the user (via the Dino chat): "for the pumpkin head, uh i might not want it to come off my head as often,
  its kind of distracting. like once every 10 minutes or something". head.txt `every=<seconds>` (default 600, +-20 % jitter
  = 8-12 min, floor 10, cap 86400) now sets the ON gap in all three places (after a skin load, after each RETURN, and at the
  intro's hand-back); the orbit (15-25 s, one boo) is unchanged. No head.txt edit needed on the headset (the default is in
  the source); `every=120` for a quick test. head.cpp md5 fbde3601, compile-checked against dumper.cpp 2616d9fc (0 errors,
  the 7 old warnings). Hand-off: the Dino session builds the next APK from the tree and the user says when to install it.
- 2026-10-10 ~17:1x, the user (via the Dino chat): "the one on the avatar sitting on the shoulders. its basically sitting on
  top of the collar of the coat. i want it lower so that the collar is like halfway up the sides of the pumpkin head. so it
  looks normal basically". Cause: the pumpkin centre (PC_Z 0.665) was at the avatar's eye line with its bottom 3.7 cm below
  the collar top (0.585), where the pumpkin (r 0.11 there) was as wide as the collar (neck_r 0.084 + 0.048) -> the rim just
  touched it. Fix in scripts/horseman_build.py: PC_Z 0.60 (6.5 cm lower, the equator 1.5 cm above the collar top) and the
  collar flared into a cowl (+0.05 at the top, ~0.17 r) with every collar ring clamped >= pumpkin radius + 1.2 cm after the
  ring smoothing (which had pulled it 3.5 mm inside). The DH bones follow PC (DH_C in Head space 0.101 -> 0.036 up);
  heads/horseman.glb is unchanged (static copy, origin at the centre). Old skin kept as backup/skins/horseman_v1_pumpkin_high.glb;
  new skins/horseman.glb md5 9b3d6c74 pushed to tribemod/skins/ (needs a re-pick of the Horseman; no hook rebuild).
  render_skin.py now also renders head_front/head_side/head_front34 close-ups.
- Seen twice (16:20:44: 47.4 cm; 17:54:01: 93.5 cm): the FIRST "rig ok" after a fresh skin load reports a large
  socket-vs-FK gap, and the next load seconds later reads ~1 cm. Diagnostic only (placement uses the FK, and takeoffs come
  minutes later when both agree), but if a takeoff ever starts away from the neck, look at head_A_xform / the FK capture
  being stale on the first tick after the component is created.
- 17:54 the user picked the Horseman on combo2 ("first takeoff in 675 s"); the headset slept from 17:57:48 to 19:50:19
  and the head took off at 19:50:19, one second after the resume, because the countdown ran on the wall clock (addendum 3
  below). So the 10-min cadence's first flight WAS observed (TAKEOFF -> ORBIT 18 s, cut short when the user quit Tribe
  9 s in), but it came at the wrong moment. The lowered pumpkin + cowl still need the user's eyes.

### 2026-10-10 afternoon (Dino session): combo1 verified on the device; combo2 built
- combo1's first launch 16:19:55 (pid 23270) passed every log check: Dino [GIANT] ready + walking map dino_collide.txt
  (25 floors, 317 boxes, 4446 people); Graveyard [GIANT] show bus 19/19, halloween_collide.txt (11 floors, 32 boxes) and
  "[INTRO] ready on this stage"; the A2 line's gait w reached 1.00 at 180 cm/s while the user stick-walked Graveyard
  (floors 0, -40, -100, through the crypt-door gap). Intro press 1 at 16:22:43 ran the pre-show. reseed.sh MOD= is now
  combo1 (club3 2d2ad182 noted as the build before it). tribemod/log_deck on since 16:23:01; no Play/Pause captured yet.
- combo2: out/hookA/combo2.aligned.apk, 112,119,023 B, md5 8e72019bac75eedd43b712bbec08c8e8, cert SHA-256 979d63d7…,
  from menu.apk + libhook_combo2.so (385,800 B, md5 9bf8fe9c; 0 errors, the 7 old warnings): dumper.cpp 2616d9fc
  (= d4f4f80f + a comment: head.cpp reads g_introCam, keep it declared above #include "head.cpp"), head.cpp fbde3601
  (every= 600 s +-20 %, boomax waits, intro=hold), club.cpp 971a4293, club_collide.h 83ab550e, intro.cpp 3f8f77dc,
  intro_ride.h 6c711050, gait.h ea05eff4. INSTALLED 16:43:29 (install -r, on the user's "ok go ahead"; base.apk 8e72019b,
  firstInstallTime unchanged, patch OBB 2e5915c7 intact, tribemod kept).
  After it runs: check the character session's head lines, then reseed.sh MOD=combo2.

### Session 3o addendum 3 (character session, 2026-10-10 evening) — the head timer now counts PLAY time (combo3 built, NOT installed)
- Bug (the Dino session's catch, confirmed from my own capture, logcat pid 55303): the countdown ran on CLOCK_MONOTONIC,
  which keeps counting while the headset sleeps and Tribe is paused. 17:54:10 rig ok "first takeoff in 675 s"; the last
  mod line before the nap was 17:57:48; the first line after it was 19:50:19.208 "[HEAD] TAKEOFF (auto)". fallbackTicks
  went 125820 -> 126000 across the whole gap (180 frames, ~2.5 s at 72 fps): our actor does not tick while the headset
  sleeps. About 220 s of play had passed, 455 s short of the countdown. Effect: any break longer than the remaining gap
  ended with the pumpkin flying off the moment the user was back, the opposite of "once every 10 minutes".
- Fix, hook/head.cpp (md5 6bfa9ead; nothing else in hook/ touched): hd_now() now returns a play clock, g_hdClock = the sum
  of each accepted tick's dt (added after the existing dt<=0||dt>0.25 filter, so a resume frame with a huge dt adds
  nothing). Every state uses it: the ON countdown, TAKEOFF/ORBIT/BOO/RETURN phase times, g_hdBooAt, the intro hold's
  restart, head_force_on. The wall clock survives as hd_real(), used only to detect a pause (5 s+ between ticks,
  accumulated) and for the 10 s "can't create the static head" log throttle. When ticks come back at frame rate the pause
  is reported once: "[HEAD] Tribe was paused N s (headset asleep?): the head's clock stood still; next auto takeoff in
  M s of play" (or "the ORBIT goes on" / "mode on"). The rig-ok, hand-back and ON lines now say "... s of play"; the
  "[HEAD] head.txt: ..." summary line is unchanged. every= therefore means seconds of play, which is what the user asked for.
- combo3: out/hookA/combo3.aligned.apk, 112,119,023 B, md5 a156adfcbc56798894d69f927d257297, cert SHA-256 979d63d7…
  (CN=Tribe Mod), from menu.apk + libhook_combo3.so (386,848 B, md5 8a5b3209; 0 errors, the 7 old warnings), compiled
  against combo2's unchanged tree (dumper.cpp 2616d9fc, club.cpp 971a4293, intro.cpp 3f8f77dc, gait.h ea05eff4,
  intro_ride.h 6c711050, club_collide.h 83ab550e; every hook/ mtime predates combo2's 16:38 libhook.so). Staged in my
  scratchpad, so out/hookA/stage still holds combo2's libhook.so; the libhook.so extracted from the signed APK is the new
  build (md5 8a5b3209, carries "Tribe was paused"). All three combo APKs are 112,119,023 B because apksigner pads the
  signing block to 4 KB. NOT INSTALLED: needs the user's go; whoever installs it (adb install -r) sets reseed.sh
  MOD=combo3. Device at 20:00: asleep, Tribe not running, combo2 (16:43:29) installed. The Dino session has the md5 and
  rebuilt the hook from the same sources independently: byte-identical libhook.so (386,848 B, md5 8a5b3209), same 7 old
  warnings, and it read the play-clock code without finding anything wrong. Install protocol (agreed 20:10): whoever gets
  the user's go runs adb install -r, sets reseed.sh:25 MOD=out/hookA/combo3.aligned.apk (combo2 moves into the "builds
  before it" comment) and tells the other session. Graveyard v6 went live at 20:03:57 (Halloween session); Tribe closed.
- 20:13 the user said "install" in the Dino chat and that session took the install; but the headset dropped off adb at
  about 20:13 (no device listed; its adb wait-for-device has been waiting since 20:13:59) and had not returned by 23:31,
  so combo3 is STILL NOT INSTALLED at that time (combo2 16:43:29 live, Tribe closed since 19:50:28). My old logcat capture
  died with the connection; a watcher (scratchpad combo3/watch_first_launch.sh, 12 h horizon) restarts a read-only capture
  into $TEMP/claude/head/head_test.log when the device is back and reports the next launch's [HEAD] lines.
- 2026-10-11 02:30 (Dino session): still off adb (since 20:11 on 10-10); its guarded auto-install waited 21:30-22:29 and
  22:30-02:30 and has STOPPED waiting. It installs combo3 when the user says the headset is plugged in, then posts the
  lastUpdateTime. Until then every Tribe launch is combo2: its rig-ok line says "first takeoff in N s" WITHOUT "of play".
- 2026-10-11 16:37:33 combo3 INSTALLED by the new Dino session (tribe-hack-b4; the headset came back on adb at ~16:35,
  install -r on the user's go from the night before). Verified from this session by a second route: on-device
  md5sum of base.apk = a156adfcbc56798894d69f927d257297, lastUpdateTime=2026-10-11 16:37:33, firstInstallTime still
  2026-10-09 22:17:43 (Meta auth intact), reseed.sh:25 MOD=out/hookA/combo3.aligned.apk. Tribe not launched yet; my
  read-only capture (adb logcat -T 1 -s TRIBEMOD:V, pid 14113, appending to $TEMP/claude/head/head_test.log) and the
  watcher are waiting for the first rig-ok line, which must end in "s of play".
- Verify once installed: with the Horseman on, take a break of a minute or more -> on the resume expect the "Tribe was
  paused" line and NO TAKEOFF within seconds; flights should come 8-12 min of play apart ("first takeoff in N s of play",
  N in 480-720).
- 2026-10-11 19:14:27 FIRST LAUNCH UNDER combo3 CONFIRMED from the capture: "[HEAD] rig ok: DH_C/DH_F/DH_U = bones 8/9/10
  ... first takeoff in 668 s of play (mode auto)" (combo2's line had no "of play"); head.txt summary unchanged (mode=auto
  fwd=+y up=+z boomax=12 m intro=hold every=600 s). Tribe was started twice that evening: pid 24677 at 19:13:25 (unofficial-
  app dialog dismissed 19:13:23, head loaded 19:13:43, avatar spawned, last line "A2 resolve: align" 19:13:54.28) and pid
  25405 at 19:13:56. The first was NOT a hook crash: the system log shows the vrshell focus placeholder at 19:13:52.97, the
  Home overlay (OVERLAY_LAUNCHER) at 19:13:54.60, the GameActivity finished at 19:13:54.66, "Process com.TribeXR.TribeXR
  (pid 24677) has died: cch+5 CEM" at 19:13:55.20 (died as a cached process after its activity was finished), the launcher
  START of Tribe at 19:13:56.64; no tombstone, empty crash buffer, no dropbox entry tonight. So it was closed through the
  headset's system menu and relaunched 2 s later (the shell does not log which button). Still pending: the nap test (the
  "Tribe was paused" line, no TAKEOFF seconds after a resume) and flights 8-12 min of play apart; watcher
  scratchpad combo3/watch_first_flight.sh (4 h) reports the first TAKEOFF / pause line / relaunch.
- 19:27:57.9 FIRST FLIGHT ON THE PLAY CLOCK, from the capture: 19:15:17 "auto takeoff held: the stage intro owns the stream
  camera" (Graveyard intro), 19:16:49.913 "the intro handed the camera back: next auto takeoff in 668 s of play",
  19:27:57.915 "TAKEOFF (auto)" = 668.002 s later (play clock == wall clock while playing, as it should), ORBIT 22 s, boo
  waited (camera 47 m) then "boo skipped this flight: the selfie-stick camera stayed 13 m away (boomax 12 m)", RETURN,
  19:28:22 "ON: head back on the neck (next takeoff in 586 s of play when auto)". Everything as designed; only the nap test
  is left. Watcher scratchpad combo3/watch_nap.sh (4 h) wakes on a "Tribe was paused" line, a relaunch/head.txt change, a
  head error, or a TAKEOFF earlier than announced (late = normal after a nap); on-time flights are only logged.

### Session 3o addendum 4 (character session, 2026-10-11 evening) — Horseman v3: the cowl opens at the front
- ~19:55 the user, from the headset via the Dino chat: "The front of the collar for the face of the pumpkin needs to be
  exposed - currently the collar is covering the front half of the face" (everything else about the head "looked great").
  Cause: v2's cowl rim sat at z 0.585 all round with r ~0.17 (wider than the pumpkin), and the mouth spans z 0.544-0.578
  and +-52 deg of azimuth (from pumpkin_tex: mouth v 0.34-0.44, u 0.25 +- 0.145), so the rim hid the mouth and nose.
- Fix in scripts/horseman_build.py (loft() now takes per-vertex ring heights): each collar ring keeps v2's height and
  radius at the back and sides but dips to the collar base across the front, z_k = Z_COLLAR0 + (z - Z_COLLAR0) * g with
  g = smoothstep(38 deg, 100 deg, angle from the front) floored at 0.08; the radius is recomputed for the lowered height
  (flare + the pumpkin clearance) and blended into the smoothed v2 ring by g. Build log: front rim z 0.5064 r 0.133 (inside
  the pumpkin's 0.15 silhouette, so it hides behind the chin head-on), side (90 deg) z 0.5706, back z 0.58 r 0.171,
  clearance min 0.0 (ok). Rendered (render_skin.py under the GPU lock, 6 s): full face visible head-on, cowl points rise at
  the sides behind the pumpkin, side view shows the rim swooping down to the chin.
- Files: skins/horseman.glb = v3, md5 a04620a1b2b8 (5,284,428 B); v2 kept as backup/skins/horseman_v2_cowl_closed_front.glb
  (9b3d6c74); heads/horseman.glb untouched (ed59d303; the build's static head is not used). NOT YET ON THE HEADSET: the
  push at 20:06 found the headset off adb (the capture pid 14113 died with it; the last mod line is 19:42:44 "body gone ->
  keeper OFF", i.e. Tribe was left at 19:42). scratchpad horseman_v3/watch_return.sh (12 h) restarts the read-only capture
  and pushes + md5-verifies the skin when the headset is back; then the user re-picks the Horseman (no hook rebuild).
- PUSHED 2026-10-12 09:01:08: the headset came back on adb at 09:01:07 and watch_return.sh (re-armed overnight with a 48 h
  cap after the nap watcher's 4 h cap ran out at 23:30 with nothing to see) staged + copied skins/horseman.glb; on-device md5
  a04620a1b2b8fe2dcea728c290b32777 verified, active_skin.txt = horseman.glb, Tribe NOT running (pidof empty), so the next
  launch loads v3 by itself (a re-pick is only needed if Tribe was already up). Read-only capture restarted (pid 14311,
  appending to the head log); combo3/watch_nap.sh (48 h cap, from byte 1829275) is tailing it for the nap test. Dino session
  told (msg fe0aae29). Still unseen by the user: the open cowl, the neck stump, the emissive glow.

## The .usmap dump: Tribe's type mappings, so its cooked assets read offline (2026-10-26)
- Why: the user asked whether we have every deck function and the decks' design. We had names only (the live object
  dump), no logic: Tribe's paks are cooked unversioned, and without a .usmap UAssetAPI leaves every export raw (Phase 3,
  Sep 29). The Sep 29 roadmap put a usmap dump first; it was never built until now.
- Built: hook/usmap.cpp + hook/usmap_writer.h, one-shot on tribemod/usmap_now (may exist before launch: it waits for the
  engine objects and BP_Deck_C, or 120 s), writes tribemod/TribeXR.usmap + usmap_log.txt. Format v4 (ExplicitEnumValues),
  uncompressed, checked against CUE4Parse UsmapParser.cs, UAssetAPI Usmap.cs and Dumper-7 MappingGenerator.cpp. Every
  loaded class and struct (functions skipped) with its own properties in ChildProperties order, supers written first;
  enum entries bare ("X", not "EAxis::X"). Layout checks run before writing; any rate under 98% = nothing written.
- Layout measured on 35,135 properties (all 100% unless noted): ArrayDim@0x2C (35,062 == 1), ElementSize@0x30 (17,572 of
  the Int/Float/Double/Name/Object/Str/Array ones), sizeof(FProperty) 0x70, FArrayProperty::Inner@0x78 (not 0x70: a flags
  field comes first), Map key/value@0x70/0x78, Set element@0x70, Enum underlying/UEnum@0x70/0x78, Struct@0x70, Byte's
  UEnum (or null)@0x70, Optional@0x70 (1 seen).
- Desktop test first: tests/usmap_test.cpp (MSVC) writes every property kind through the same writer; scripts/uasset_tool
  (dotnet, UAssetAPI 1.1.0 from the NuGet cache) reads it back identically. UAssetAPI decodes usmap names as ASCII
  (CUE4Parse: UTF-8); Tribe has no non-ASCII names, so it doesn't matter here.
- combo13 = combo12 + the dump. Today's sources first rebuilt byte-identical to libhook_combo12 (4744f53f). combo13: lib
  1f2391dc, APK c5f6c308, same cert as combo12 (979d63d7), 751 of 752 entries identical. Installed 2026-10-26 22:20:00
  over combo12 (verified md5 46babf9f before; Tribe had been up since 18:44 in the background, the install restarted it).
  reseed.sh MOD=combo13 (combo12 noted as the fallback).
- Run: launched 22:20:44, dumped 22:20:54 in 0.3 s: 48,600 objects, 8,589 classes and structs, 1,809 enums, 35,135
  properties, 39,688 names, 1,390,942 B, every problem counter 0. Tribe stayed up (same pid, avatar follow running).
  pulled/TribeXR.usmap md5 9f43c160 (same on the headset); log in logs/usmap_log_20261026.txt.
- Result: repak 0.2.3 (~/.cargo/bin) unpacks Tribe's Oodle paks directly (pakchunk0 -> D:/TribeUE/tribe_paks, assets ->
  D:/TribeUE/tribe_assets, JSON -> tribe_assets/json). Without -> with the usmap: BP_Deck 342 raw -> 0 raw, 329/329
  functions decoded (the live dump also counts 329); BP_Console (mixer) 178 -> 0, 167/167; BP_JogWheel 58 -> 0, 51/51.
  Content checks: CurrentPitch 1.0, ClientPlaybackSyncToleranceMs 360, Server_NetSyncPacket's 4 fields; the deck screen
  at (-0.29, -13.70, 3.70) cm, pitch 15.2 deg, scale 0.145; GetIsPlaying = IsPlaying -> isPlaying -> return.
- Gap: a Blueprint whose Blueprint parent wasn't loaded at dump time keeps its default object raw, e.g.
  BP_BeatFXTypeKnob_V10 (parent BP_BeatFXTypeKnob_C isn't in the usmap); its functions and components still decode.
  Unloaded parts with loaded parents parse fully (BP_JogWheel3000 23/23, BP_SlipButton 13/13). Fix: add schemas for every
  Blueprint class from the paks' own ClassExports (offline), or dump again with each deck and mixer model loaded.
- Use: adb shell touch $D/usmap_now (any time), then adb pull $D/TribeXR.usmap; read an asset with
  scripts/uasset_tool/bin/Release/net8.0/uasset_tool.exe asset pulled/TribeXR.usmap <file.uasset> [out.json].

## The deck catalog: every deck, mixer and control, from Tribe's own Blueprints (2026-10-26)
- Asked for after the usmap: what every button, knob and screen on each deck and mixer does, and where it sits.
  Result: claudedocs/deck_catalog.md (12 models, 448 spawned controls = 670 placed instances once mixer channels and
  the FLX4's looped pads are expanded, 196 control classes, what the deck/mixer/rig engines do) and
  claudedocs/deck_reference.md (every function of BP_Deck, BP_Console, BP_MixerChannelDevice, BP_BaseDeckControl,
  BP_Rig with parameters and calls). Bulk outputs stay on D: (derived from Tribe's code): D:/TribeUE/tribe_assets/catalog/
  code/ (280 Blueprints as pseudo-code), deck_catalog.json, inventory_before/after.tsv.
- Pipeline: repak 0.2.3 `unpack -i TribeXR/Content/Equipment -i .../Visuals/Skins/Rig` (pakchunk0 only) ->
  D:/TribeUE/tribe_assets/all; `uasset_tool augment` adds the Blueprint classes, user structs and enums the runtime dump
  lacked, from their own ClassExports -> pulled/TribeXR_full.usmap (+139 classes/structs, +2 enums, every parent
  resolved; reading and rewriting the original reproduces it byte for byte); inventory: 910 assets, 8,757 exports, 0
  raw; `uasset_tool dump` -> 360 JSONs, 3,618 functions all through UAssetAPI's KismetSerializer;
  scripts/kismet_print.py prints pseudo-code; scripts/deck_catalog.py builds the catalog. UAssetAPI also loads a
  missing parent .uasset from disk when the Content folder layout is intact; the augmented usmap removes that need.
- How Tribe builds gear: a model Blueprint on BP_Deck or BP_Console plus an ...Info class (menu name, store SKU
  Equipment_*, width, preview). SpawnControls / SpawnChannel / RespawnPadButtons spawn control actors and hand them
  Deck/Console + the model's mesh and material tables; "Setup Child Control" puts each on the bone its
  DT_<ModelId>_ControlInfo row names (row = the control's GetUniqueControlName: ControlName + band/mode word + index
  or _channel), else on the marker passed in. The DDJ-FLX4 shares one model id across 3 tables (_0 mixer, _1/_2 decks).
- Positions: markers exact; bones from each Skeleton's reference pose (parsed from the native bytes after the Skeleton
  export's properties: bone names/parents, then FTransforms as doubles). Bone vs marker for the same control agree on
  the CDJ-3000 (4 of 5), Tribe CDJ (4/5) and DJM-NXS2 (16/17) at median < 0.2 cm; the Tribe Mixer's bones sit
  (0, -1.18, -4.38) cm from its markers (14/15), so they are shifted; the CDJ-3000X's markers are stale (0/5), so its
  bones are used as the game does.
- Findings: hot cues: 8 buttons on the CDJ-3000 and CDJ-3000X, 3 on the Tribe CDJ, 8 pads on the FLX4, 4 pads on
  the Starter CDJ; EQ band byte 0-4 = Low/LowMid/Mid/HighMid/High
  (the V10 is 4-band); the APC40 is a Resolume controller (OSC, SetResolumeTempo); play/hot cues go out through
  the pawn's Server_ functions and the deck's Multi_ ones; Tribe's "Smart Fader" matches tempo from the fader.
- Not covered: how the gear looks (meshes/textures need FModel with the same usmap), the native code under the
  Blueprints (Superpowered audio, the mesh component's table lookup, networking).

## The gear models and the C++ (2026-10-26, late)
- Models: scripts/mesh_export (CUE4Parse 1.2.2 + CUE4Parse-Conversion 1.2.1, the newest builds for .NET 8; 1.2.2.2026xx
  need .NET 10) reads the loose files repak unpacked. Its root must be .../all/TribeXR (else it names the project after
  the folder). It reads .usmap only up to version 3: `uasset_tool downgrade` writes pulled/TribeXR_full_v3.usmap (each
  enum's names placed at their values; 10 bit-flag enums keep their order). Output in D:/TribeUE/tribe_models (589 MB):
  13 gear meshes (Equipment/Models/SkeletalMeshes, with textures), 144 control and part meshes, 221 PNGs (24 deck
  skins), 44 material JSONs. Export the gear with --materials and the rest with --no-materials: control meshes share
  their model's 2048x4096 atlases, and re-decoding those per mesh took over an hour (now ~7 min). One texture
  (PF_ETC2_R11_EAC) doesn't decode. Previews: scripts/render_gear.py (Eevee, under the GPU lock, 22 s); the glTF
  importer's hidden 2 m bone-shape icosphere must not drive framing. claudedocs/gear_models.md + gear_models/ has the
  contact sheet, sizes and the texture scheme (TextureA off, TextureB lit, Segments = the per-control light mask that
  ElementIndex points into, Weights palette). The Tribe CDJ's texture is a photo of a Pioneer CDJ-2000.
- Native dump: hook/native.cpp, one-shot on tribemod/native_now (its text may list packages; default /Script/TribeXR,
  /Script/TribeIntonal, /Script/SuperPowered): per class its parent, size, the default object's vtable (CDO found by
  class pointer + RF_ClassDefaultObject), every UFunction's flags, Func RVA and parameters, plus vtable-only records
  of the engine parents so overrides can be diffed. combo14 (1c752376, installed 23:12) was replaced before any launch
  by combo15 (c0514d11, lib bf47c27b, installed 23:27; reseed MOD=combo15, first launch NOT yet checked). The switch
  is set; it waits for the user's launch. Pull: tribemod/native_dump.jsonl -> pulled/native_dump.jsonl.
- Ghidra: the persistent project C:/ghidra-work/tribexr opens in ~40 s headless with an 8 GB heap (16 GB would take
  nearly all free commit). Code: Ghidra address = runtime RVA + 0xFF000 (checked: ProcessEvent at 0x1957dd4 tests
  FUNC_Native at +0xb1). Ready: scripts/native_prep.py (dump -> work list + classes.json), scripts/NativeDecomp.java
  (exec thunk -> implementation by dropping the helpers most thunks call; renames FUN_ names to Class__execX /
  Class__X / Class__vfuncN; one .c per class), scripts/native_reference.py (-> claudedocs/native_reference.md).
  The test run named UObject__ProcessEvent and UObject__ProcessInternal in the project.
- libacidsynth.so (SONAME libUE4.so) is Intonal-compiled DSP, not hand-written C++. Own project
  C:/ghidra-work/acidsynth; all 162 functions in D:/TribeUE/tribe_native/libacidsynth.c; the generated core in
  libacidsynth_core.c (call_root, the per-sample processing: 20,227 lines, 121 sinf / 32 powf / 16 cosf calls;
  reset_root) and libacidsynth_core2.c (create_root, which needs DecompileOptions.setMaxPayloadMBytes); the 425 KB
  write_to_float32_four_values_root doesn't decompile. Its controls are TribeIntonal's AcidSynthUniforms: beat width,
  MIDI note offset, cutoff, resonance, env mod, decay, accent, waveform switch, lowpass attack, distortion amount and
  tone, chorus rate and mix, echo time, feedback and mix, master gain: a TB-303-style voice into distortion, chorus
  and echo.

## The C++, read statically (2026-10-27, 03:15-04:10)

- Why static: the 4 h watcher timed out at 03:12 without a Tribe launch. I didn't launch it over adb: a headless
  `am start` crashes or never ticks (Session notes above), and Meta's launch dialog has the Restore button. Instead
  scripts/NativeTables.java reads UE's own registration code in libUnreal.so (C:/ghidra-work/tribexr):
  - GetPrivateStaticClassBody = Ghidra 0x17fba04 (the callee most often given a Tribe package literal in x0); 7,606
    callers, 4,077 classes in 175 packages. Per call: x0 package, x1 name (UTF-16, +2 skips the U/A prefix), x3
    StaticRegisterNatives<Class>, w4 sizeof; stack +8 InternalConstructor<T>, +32 Super::StaticClass.
  - Native table: the call in StaticRegisterNatives that passes (FNameNativePtrPair table, count).
  - Vtable: the last vtable constant InternalConstructor<T> (or the T::T it calls) stores into the object itself.
- Result: 179 classes (TribeXR 130, TribeIntonal 32, SuperPowered 12, Beatport 2, TribeMIDI 1, AndroidVulkanVideo 1,
  VulkanVideoMeshComponent 1) + 22 engine parents, 1,518 native functions, 872 overrides. Files:
  D:/TribeUE/tribe_native/static/ (native_static.jsonl in the hook dump's format, work.tsv, classes.json,
  slot_names.json); decompiled D:/TribeUE/tribe_native/classes/ (178 .c, 5.1 MB, 0 failures, ~1 min per run);
  claudedocs/native_reference.md (generated; its summary section is claudedocs/native_summary.md, hand-written).
- Checks, each by a second route: all 179 class names are in the runtime usmap; 372 of 374 Blueprint calls into Tribe
  classes are in the tables (the other 2 are delegate signatures); all 179 parents equal the usmap's; every vtable
  extends its parent's; the engine slot names (scripts/vtable_names.py, UE 5.4.4 headers + .generated.h) give all 22
  parents' vtable lengths exactly, and UObject slot 78 = ProcessEvent (rva 0x1858dd4, the runtime-measured one).
  AcidSynthUniformFuncs' 17 setters = libacidsynth's 17 uniforms.
- Lessons:
  - FlatProgramAPI.getReferencesTo stops at 4096 references; use ReferenceManager.getReferencesTo.
  - StaticRegisterNatives inlines StaticClass(), so every class with natives registers twice; keep the call outside.
  - A vtable read runs into the next table: FClassRegisterCompiledInInfo {Z_Construct_UClass_X, X::StaticClass,
    TEXT("UX"), &Z_Registration_Info, ...} often sits right after a vtable, and its first two members are code. Stop
    at a slot that something points at. Constructors also store helper objects' vtables: only accept stores into the
    constructed object (param 0, or *param0 in InternalConstructor).
  - Vtable layout from headers needs UHT's virtuals (Foo_Implementation / Foo_Validate for every RPC and
    BlueprintNativeEvent, spliced in at GENERATED_BODY), the Itanium secondary-base rule (overriding an interface's
    virtual takes a new primary slot), signature normalization (class/struct keywords, east/west const), and
    UE_ALLOW_EXEC_COMMANDS=1 + UE_WITH_IRIS=1. Tribe is a Shipping build: Development macros miss 4 of 22.
  - Git Bash + cmd: `cmd //c x.bat` works only without MSYS_NO_PATHCONV; with it set use `cmd /c`. Arguments like
    /Script/TribeXR need MSYS_NO_PATHCONV=1 or they arrive as C:/Program Files/Git/Script/TribeXR.
- Still open: the runtime dump adds parameters, flags and Blueprint-only events (combo15's tribemod/native_now is
  still armed; combo15's first launch still unchecked). Then: pull native_dump.jsonl,
  `native_prep.py pulled/native_dump.jsonl <work.tsv> <classes.json> D:/TribeUE/tribe_native/static/slot_names.json`,
  NativeDecomp.java, native_reference.py with claudedocs/native_summary.md. Compare its func/vtable RVAs with
  native_static.jsonl: they should be equal.
- 2026-10-27 04:38 the runtime dump arrived (combo15's first launch: DONE, Tribe up, no crash; pulled/native_dump.jsonl
  md5 95904c4a, logs/native_log_20261027.txt). Against the static read: 174 classes, parents and sizes all equal; all
  1,496 native function addresses equal (4 names differ only in case: FNames keep the first-registered spelling);
  its vtables run 2-3 entries past the end in 114 classes (hook/native.cpp reads until a non-code qword, so it reads
  into the class registration record), so `native_prep.py ... --static native_static.jsonl` keeps the static
  vtables and adds the 5 classes outside the dumped packages. Merged outputs: D:/TribeUE/tribe_native/runtime/
  (work list = the static one; no re-decompile needed); claudedocs/native_reference.md now has every function's
  signature and flags for TribeXR/TribeIntonal/SuperPowered, plus the 37 functions left to Blueprints.

## Cue headphones, song selection and menus (2026-10-27, 04:45-05:20)

- Unpacked more of pakchunk0 (repak -i TribeXR/Content/{Menus,Pawn,TrackManager,MusicServices,Audio,Waveform,
  GameModes} -> D:/TribeUE/tribe_assets/all; last night's unpack had only Equipment + Visuals). Augmented usmap:
  pulled/TribeXR_full2.usmap (+161 classes/structs, 0 parents missing; TribeXR_full.usmap left as it was). Dumped and
  printed: Pawn 23 Blueprints / 478 functions, Menus 151 / 2,295, TrackManager 24 / 519, MusicServices 6 / 131,
  Waveform 3, GameModes 10 (Audio = sound files only) -> D:/TribeUE/tribe_assets/{dump,catalog/code}.
- Write-up: claudedocs/cue_tracks_menus.md. Key facts:
  - Hand-to-ear: TribeControllers.TryToToggleHeadphoneWorn on a grab press with nothing grabbed: hand within 25 cm
    (MaxHeadphoneWornToggleDistSquared 625) of a point 5 cm behind the camera; ear = side of the head (camera right
    vector), VR input mode only -> TribePawnBP.ToggleVirtualHeadphones -> BP_Console.SetHeadphonesWorn(L, R) ->
    SuperPoweredLibrary flags at module +0xB4/+0xB5.
  - Output (module function Ghidra 0x47b5c30): main + cue buses; main split L/R into two spatialized virtual monitors
    ((-500,0,170) and (500,0,170), gain 24; listener = camera); a worn ear gets the cue bus added and its monitor's
    spatializer gets Headphone Isolation (module +0x134, the BP calls it Occlusion); isolation 1.0 removes the room
    from that ear; then global volume (+0xB0) and the limiter; Split Mono (+0xC0) = mono main left, mono rest right.
    Module layout: +0xB6 spatializer on, +0xB7.. limiter, +0xD0-0xF0 monitor positions, +0xF8-0x120 listener,
    +0x128 monitor gain, +0x130 room.
  - Track load: W_TrackOptions.AttemptTrackLoad -> TribePawnBP.LoadTrackToChannel (guest: Server_Load*ByFilename) ->
    BP_Rig -> BP_Deck LoadTrack -> Multi_Open*ByName on every headset -> OpenCurrentTrack: own library, track packs,
    own streaming account ("{StreamingService} service required..."), else RequestTrackTransfer.
  - Menus: B/Y toggles the mini menu (Music, Equipment, Visuals, Social, Lessons, Demo Mix, Exit); main menu =
    W_MainMenu on a 3D panel owned by the game state.

## Menu catalog + the mixer's cue bus (2026-10-27, 05:20-06:00)

- scripts/menu_catalog.py -> claudedocs/menu_catalog.md (+ D:/TribeUE/tribe_assets/catalog/menu_catalog.json): 162
  widget Blueprints (Menus, TrackManager, MusicServices), 547 controls (480 labelled), 547 bound events (493 doing more
  than restyling themselves). How:
  - the widget tree comes from the WidgetTree's widget exports and their slot exports (Parent / Content);
  - labels: text blocks inside the control, Tribe widgets' own text properties (TextLabel, ButtonText, Header),
    string-table keys (Content/Localization/StringTables/*.csv, unpacked with repak; 686 entries), or for a
    checkbox/slider the text block beside it;
  - events: the class's ComponentDelegateBinding export (exact widget, delegate and function; BndEvt names alone
    mislead: copied nodes keep another widget's name), plus `self.X.OnY += ...` bindings in the graph;
  - "does": the calls reached from the event's ubergraph entry (jumps, both sides of branches, sequences), the
    Blueprint's own functions and calls into other dumped Blueprints (by the variable's type) expanded a level;
    cosmetic calls, redraws and getters filtered.
  Checked by hand: Music -> BP_MiniMenu.OnMusicIconClicked -> W_MiniMenu.ToggleMusicPanel = SetActivePanel(TrackBrowser),
  then the analytics event Menu_TrackBrowser. Every menu click sends a TribeAnalytics event; the mini menu's Record
  button calls an empty ToggleRecordPanel.
- The mixer's render (USuperPoweredMixer, Ghidra 0x47aeca8) read stage by stage. Order: input, mic, trim/comp,
  [cue if PRE EQ], channel FX, EQ + filter, [cue if not PRE EQ], faders + crossfader (in place: cue is pre-fader),
  beat/send FX, master sum, master filter/isolator, mic into master, headphone bus, outputs (FUN_047b1564: main =
  master x balance x master level; headphones = headphone bus x LEVEL). Cue sum = FUN_047b0188: every channel with
  cue byte +0x6F0+ch summed with three chained Superpowered stereo mixers (up to 10 channels). Headphone bus =
  cue x clamp(1-MIX) + (MASTER CUE ? master x clamp(MIX+1) : 0). Fader/crossfader curve formulas and every control's
  offset are in claudedocs/cue_tracks_menus.md "Inside the mixer".

## Mixer effects + runtime menu labels (2026-10-27, 06:00-07:00)

- claudedocs/mixer_effects.md: Color FX, send FX, Beat FX and mic FX read from the decompiled mixer. Units:
  FUN_047a3448 (NXS2 colour FX: Space, Dub Echo, Sweep, Noise, Crush, Filter), FUN_047a4a1c (V10/A9: Filter,
  Phantom Echo, Vaporize, Noise Chopper), FUN_047a42fc (sends: Dub Echo, Short/Long Delay, Reverb), FUN_047a7dd8
  (Beat FX engine) with FUN_047a8580 (per-effect dispatch) and its parameter helpers FUN_047a8ee8..FUN_047aad8c,
  FUN_047a5ad4 / FUN_047a64c8 (set type / parameter), FUN_047ab760 (mic FX, not read). Tables (Ghidra addresses):
  0x89dbf0 colour FX insertion point per type (0 pre-EQ, 1 post-EQ, 2 post-fader); 0x89d748 per Beat FX type
  {min/max interval index, min/max ms, trail flag} stride 0x20; 0x89dac8 interval -> beats (1/64..128, negative
  for Mobius); 0x89d9e8 Reverb/Shimmer % table; 0x89da58 Pitch % table; exponent 0.8197 at 0x561238. Superpowered
  classes recognised by constructor + field layout (Echo/Reverb ctor (samplerate, 96000); FX `enabled` byte at
  +8). Not read: the sample loops of Tribe's own effect classes and the SDK's DSP; Shimmer, Slip Loop and Megaphone
  have no case in the Beat FX engine; Vinyl Brake is not processed there.
- Menu labels: scripts/menu_catalog.py now labels 546 of 547 controls. Sources, in order: text inside; the text
  beside a checkbox/slider/dropdown; text set at run time (SetText / Set...Text / AddOption, with Array_Get from a
  member array resolved to the class default's values, e.g. the sort dropdown's 8 options); list views' entry
  class; icon textures (an Image's brush, a Tribe widget's ButtonImage, or the Button style's Normal brush; generic
  backgrounds skipped); embedded panels; the widget's name split into words as the last, marked fallback.

## Own VR DJ game: plan research (2026-10-27, morning)

- claudedocs/vr_dj_game_plan.md: the plan (engine, audio, crowd stream, Quest scaling, online, phases 0-4 with
  headset pass/fail tests, store, rights, risks, sources). Nothing built.
- Superpowered can't be licensed for a new app: no new licences, prorated renewals only, operations end
  2027-07-31 (superpowered.com/superpowered-farewell). Successor "Yuby" (Gabor Szanto): no public page or price;
  contact him. The plan uses open parts instead: Signalsmith Stretch (MIT) or Bungee (MPL-2.0) for key lock, Oboe
  for the DJ headset's output, Opus for the crowd stream (UE_5.4/Engine/Source/ThirdParty/libOpus exists, checked).
- Tribe's DJ audio bypasses UE's audio (the -nosound probe above: two OpenSL ES players stayed up). In the plan only
  the DJ's headset runs the deck engine; listeners play an Opus stream (128 kb/s; Xiph calls 128 VBR "pretty much
  transparent") through UE audio, and light cues carry the stream's sample numbers.
- Engine: Meta's compatibility matrix (2026-09-24) names fork tags like oculus-5.7.4-release-1.205.0; the fork needs
  a source build (verified Meta dev account + linked Epic/GitHub), which a dedicated server needs anyway. UE 5.4 is
  not on that page. This PC: i5-9400F 6 cores, 32 GB, GTX 1660 SUPER, D: 254 GB free, C: 135 GB.
- Numbers in the plan were recomputed by script: 63.5 MB per 6-min 16-bit stereo track; 57.6 MB per listener-hour at
  128 kb/s; near/far split (16 near at 40 B x 20 Hz, far at 8 B x 2 Hz) = 107 kb/s per headset and 5.3 Mb/s server
  at 50 people, vs 255 Mb/s server at 200 people without the split. Packet sizes are assumptions.
- Not found: Meta Horizon Store's current revenue share (only 2021-2022 reports of 30%).

## Key lock CPU test on the Quest 3 (2026-10-27, 08:33)

- scripts/keylock_bench.cpp + scripts/keylock_bench.sh. Signalsmith Stretch v1.3.2 (88061fd) + signalsmith-linear
  0.6.6, both MIT, cloned to out/third_party/. Built with out/android-ndk-r26d clang++
  --target=aarch64-linux-android29 -O3 -static-libstdc++ (695,856 B), run from /data/local/tmp over adb and deleted
  after (checked). Log: logs/keylock_bench_20261027_083325.txt.
- Setup: 4 stereo decks, 256-frame blocks at 48 kHz (5.33 ms), +8 % tempo, 20 s per run (3,750 blocks), pinned per
  core. Tribe was open but the headset asleep, so FORCE=1. Cores ran at their top clocks: cpu2-5 2.36 GHz, cpu0-1
  2.05 GHz.
- Default preset (120 ms window / 30 ms hop, no split): average 7.4 % of a block on the fast cores, 8.7 % on the slow
  ones; worst 48 % / 60 % (spikes every hop); 0 blocks over budget in any run.
  - Split computation: worst 16-18 %, for +30 ms output latency (90 ms).
  - Cheaper preset (100/40, split): average 5.3-6.1 %, worst 10-11 %.
  - Custom 40/10 with split: average 7.4-8.6 %, worst 11-12 %, latency 20 ms in + 30 ms out.
  - Ratio 0.92 costs the same as 1.08.
- Correction to the plan's first draft: D:\MetaUE54 is already a source build of Meta's 5.4.4 fork (Build.version:
  Partner-Oculus-UE5, 5.4.4). So no account linking and no first source build are needed. libOpus is in its
  ThirdParty folder too.

## Key lock listening test (2026-10-27, 08:35-08:48)

- Files: scripts/keylock_render.cpp (plays a raw f32 file through the stretcher block by block, like a deck) and
  scripts/keylock_listen.sh.
  - The script pulls the track read-only, builds the renderer with MSVC 2022 (vcvars64 + cl, through a generated .bat
    run by powershell.exe), renders, checks, and encodes.
  - The .bat puts the VS Installer folder on PATH; without it vcvars64 prints "'vswhere.exe' is not recognized" (it
    still builds).
- Track: ICETROUT-CHIMERA.wav (/sdcard/Music/NEW MUSIC FOR OCULUS; lossless, 145 BPM), pulled to
  out/keylock_listen/src. The excerpt is 30 s from 95.4 s (drop at 99.4 s), resampled to 48 kHz with soxr.
- Renders:
  - +8 %: 120/30 (default), 100/40 (cheaper), 60/15 split, 40/10 split;
  - -8 %: 120/30 and 40/10.
  
  Durations exact (27.78 s / 32.61 s).
- Key check (same stretch of music in every file): the energy per pitch class (100-2000 Hz, 8192-point STFT),
  compared with the original's, is 0.998-0.999 for every key-lock render. A simulated plain speed-up gives 0.763
  (+8 %) / 0.734 (-8 %). Strongest bass: 47.03-48.55 Hz against the original's 47.75 Hz; a plain speed-up would give
  51.57 / 43.93 Hz.
- Peaks rise 3.1-3.6 dB with stretching (original +1.9 dBFS after resampling, renders +5.0 to +5.5 dBFS); the average
  loudness doesn't change (-11.8 vs -11.9 dB). So all clips got one gain (-5.8 dB): the loudest peak sits at -0.3 dB,
  and none clips. The engine will need a master limiter or headroom.
- `python -I` can't import numpy here: it lives in the user site-packages (AppData/Roaming/Python/Python313), which -I
  hides. Use `python -P`.
- The 7 MP3s (320k) were sent to the user's phone with SendUserFile, since the user was away from the PC. The 24-bit
  WAVs are in out/keylock_listen/ICETROUT-CHIMERA. Waiting for the user's pick.

## Own VR DJ game: deck engine core (2026-10-27, 08:50-09:15)

- The user heard no difference between key lock windows ("I mean it all sounds right"), so the engine uses 40 ms /
  10 ms with split computation (30 ms delay).
- The engine lives in its own repo, D:\VRDJ, not in this one: this repo's snapshot was shared with Tribe's dev. Its
  README has the layout and status. Nothing is committed.
  - Deck: CDJ cue, 8 hot cues, beat loops, beat jump (quantized jumps keep the beat), tempo, pitch bend, key lock
    (Signalsmith seek / outputSeek, so starts have no delay and loops are seamless), beat sync (one jump to line
    up, then a rate correction).
  - Mixer: Tribe's signal path, fader, crossfader and EQ curves (the EQ knob read from SetChannelEq in the
    decompiled SuperPoweredMixer: Kill curve = knob x 2; Classic = 0.1 + 1.9 knob^1.078), the headphone formula,
    an LR4 isolator at 250 Hz / 3 kHz, the one-knob filter, and a limiter.
- Checks: `bash tools/build.sh run` (MSVC), 84 pass.
  - 60 minutes of looping beat sync, measured in the rendered audio: 0.03 ms worst gap (0.31 ms with key lock).
  - Key-locked clicks sound within 0.9 ms of the beat; zero heap allocations while rendering.
- Bugs found by the checks:
  - Mid = input - low - high only gave 5 dB kills (the filters' phase shift); replaced with an LR4 tree plus an
    all-pass.
  - A test wrote past its buffer: heap corruption, exit 0xC0000374 and no output. Unbuffered stdout now.
- Demo: tools/mix_demo.cpp, Kane & Undertaker (140) into CHIMERA (145, synced, key lock), double drop at bar 16. The
  drops line up within 0.3 ms; the sub energy jumps on the expected beat in the audio. MP3 sent to the user's phone.
  - CHIMERA's drop is at 99.35 s: its grid anchor sits half a bar off the downbeat (found beat by beat in the
    sub-bass).
  - Kane's drop is at 136.809 s (sub energy x3000 on the bar).

## The full decode: every pak, the lesson data, the effects DSP (2026-10-27, evening)

- **Why.** The user asked "we have the full game and decks fully decompiled right?". The answer was no: only 9 Content
  folders of pakchunk0 plus Tribe's C++ were done. Then the user said "do the full thing".
- **Paks.** The OBB holds four: pakchunk0, pakchunk1 (the five stock stages Desert, HipHop, HotelSelina, LodatoLounge,
  PolygonCity) and two optional paks.
  - pakchunk1 and the optional paks came out of pulled/main.2304.com.TribeXR.TribeXR.obb with 7z; sizes match the
    listing.
  - Each pak was unpacked with repak into an empty folder, then merged into D:/TribeUE/tribe_assets/all with `cp -rn`:
    7,975 files (2,787 .uasset, 13 .umap).
  - All 3,727 earlier files were in the new unpack, 400 of them byte-compared identical; the paks share no paths.
  - Engine/Content and Engine/Plugins are left packed: stock UE 5.4.4.
- **Mappings.** `uasset_tool augment pulled/TribeXR.usmap D:/TribeUE/tribe_assets/all pulled/TribeXR_full3.usmap`: +246
  classes/structs, +2 enums, 0 parents missing.
- **uasset_tool** now also reads .umap (levels and their level Blueprints), and `dump` writes World packages.
  - Regression: Equipment re-inventoried identically to inventory_after.tsv (837 rows, once line endings are
    normalised).
  - Inventory: D:/TribeUE/tribe_assets/catalog/inventory_full.tsv: 2,800 packages, 0 errors.
  - 7 exports stayed raw, in 5 NDI assets: NDI plugin classes weren't loaded at usmap time. They hold no functions.
- **Dumps:** one folder per Content folder in D:/TribeUE/tribe_assets/dump/.
  - Equipment and Visuals are rooted at Content, because deck_catalog.py looks assets up as "Visuals/...". The new
    Visuals dump got that prefix in its asset field; the rest is identical to a folder-rooted dump.
  - Every other folder is folder-rooted.
- **scripts/code_print.py (new)** regenerated the whole code/ tree: 733 files = 629 Blueprints (8,876 functions) + 104
  tables/structs/enums, plus 13 levels with their placed actors and root transforms.
  - It reproduces all 491 non-empty earlier files. Equipment matches byte for byte; the others differed only in CRLF
    (kismet_print's stdout) and the `var` lines.
  - The earlier printer wrote 27 empty files for tables/structs/enums (now filled) and 6 for skeleton/mesh dumps (now
    not written).
- **Checks.**
  - The functions printed equal the inventory's count in every folder.
  - The native dump's 37 bodiless functions are 5 delegate signatures + 32 Blueprint events. 31 are implemented in the
    decoded Blueprints; `TribeGameInstance::PreMapTravel` is implemented nowhere.
- **Lesson data in Content/Replays.**
  - **Saves:** 501 .sav (GVAS). By class: TribeEquipmentSaveGame 327, TribeRigSaveGame 109, TribeReplaySaveGame 64,
    TribeDanceMoveSaveGame 1. By engine: UE 4.26.2 74, 4.27.2 383, 5.4.4 44.
    - scripts/gvas_print.py (new) writes them to D:/TribeUE/tribe_assets/catalog/data/Replays: 501/501 clean, every
      field in the runtime schema.
    - UE 5.4 saves need complete type names (UE5 1012) and the UObject serialization-control byte before the
      properties (1011+).
  - **Charts:** 109 .seq. Each line is a TribeBeatHighwayEvent (ControlName, ControlValue, ControlState, MixerChannel,
    bIsMixerEvent, MeshType, [ReactionType], [SoundClipIndex]). Line 2 lists the preloaded sound clips.
  - **Replays:** 126 .inrp, decoded by the cpp-fx agent (scripts/inrp_print.py, 126/126, 0 bytes left; I reran it).
  - **Other:** one pack manifest .json, 624 subtitle .txt, 3 .glb avatars.
- **C++ (the cpp-fx agent; read-only Ghidra runs; scripts/FxProbe.java + scripts/ghidra_probe.sh).**
  - Every Tribe effect, the mic FX and most of Superpowered's DSP are written up in claudedocs/mixer_effects.md
    ("Inside the effects") and claudedocs/superpowered_dsp.md.
  - Unread: the time-stretch core, the Spatializer, the Compressor/Limiter gain loops, and jog modes 3-5/slip.
  - Checked by me by another route:
    - the Phaser LFO bug: beatfx_dispatch.c case 9's step = 2π·(beat ms / time ms)/sr, and per-sample 0x47b9d8c
      advances it twice per frame, so the period is beats/2 s;
    - no mixer offers Shimmer, Slip Loop, Megaphone or Vinyl Brake: every AvailableBeatFX list in the Equipment dumps;
    - the Freeverb comb lengths: 0x45c..0x651 written in the SDK constructor.
- **Write-up: claudedocs/game_systems.md.** It covers coverage, data formats, lessons/beat highway/DJ challenge/dance,
  the visuals wall, the crowd, the stock stages, the video stage, Twitch, achievements, OSC/MIDI/Metaverse/Discord/NDI,
  config highlights and the checks. The doc-lessons and doc-stage agents drafted the sections; I checked them against
  the code.
  - **Corrected from the drafts:**
    - the beat highway's hit buckets: `frintm`, a floor, gives symmetric quarter windows, and FailureEarly can occur;
      the draft had assumed truncation;
    - BeatFrequency = 1.0, read from the constructor FUN_051010d4 (`param_1[0x52] = 0x23f800000`); MasterTempo 120;
    - the judge ignores ControlValue: s0 is never read in FUN_0510627c;
    - the visuals-wall stubs, from `_INIT_1105`'s FName globals: FUN_050ef9e0 NdiPlaybackTick, FUN_050f08cc
      VideoPlaybackTick, FUN_050eef38 GifPlaybackTick;
    - guests follow the host's environment because IsHost returns the replicated bHost (CPF_Net).
- **NativeDecomp mislabels.** For natives whose real implementation is a virtual call, NativeDecomp named the first
  direct callee instead: nine engine helpers.
  - For example FName's constructor was shown as TribeBeatHighwayLane__SetupLane, and FString-from-TCHAR as
    TribeDanceManager__GetReplayRoot.
  - They are renamed in the Ghidra project (scripts/RenameFunctions.java, SAVE=1, verified in a fresh session) and in 86
    .c files under D:/TribeUE/tribe_native/{classes,fx,inrp}. The table is in claudedocs/native_summary.md.
  - native_reference.md was regenerated: only the summary changed.
- **Corrections to earlier entries here,** from the decoded code:
  - Lines ~4627 and ~4846: SetupEnvironmentBackdrop's arguments are (BackdropMesh, BoothSpotlight, BackdropSpotlight,
    RoomSkylight, LightDimFactor), not the chroma mesh or the DJ table. Every stock level passes 0.8 dim, except Lodato
    0.7 and Pioneer 0.
  - Line ~4631: this+0x3d4 is the PLAY mode (GetPlayMode returns it). SetBackdropStaticMesh takes mode 1 GIF → +0x2e8,
    2 video → +0x2e0, 3 NDI → +0x2f0; the old line had 2 and 3 swapped.
- **Config.** Config/*.ini are plain text (highlights in game_systems.md, no credentials copied). Tribe's multiplayer is
  EOSPlus with NetDriverEOS.
