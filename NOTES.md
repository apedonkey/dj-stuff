# Tribe XR avatar-loading recon

Read-only static analysis of Tribe XR as installed on my own Quest 3. (CONSTRAINT LIFTED 2026-09-29:
the read-only / no-reinstall rule below held through the analysis phases; the re-sign gate has since
passed [verdict a — a re-signed stock build launches, logs in past Meta entitlement, renders — burner
account] and the injected-hook route is authorized. Keystore: tribe.keystore, pass tribexr. See the
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
