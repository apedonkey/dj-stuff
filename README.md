# Tribe XR mod

A native mod for Tribe XR on Meta Quest, built against Tribe 0.12.5.1 (versionCode 2304). It adds:

- custom characters with full-body tracking;
- four extra stages, three of them with lasers and moving heads that follow every song;
- walking on those stages;
- a flying stream camera.

It works by injecting one library, `libhook.so`, into Tribe's APK. Tribe's own code is unchanged.

**Start with the guide, [claudedocs/GUIDE.md](claudedocs/GUIDE.md).** It covers what the mod does, how it works, how to install it, every setting, how to rebuild each part, and what we learned about Tribe and Meta along the way.

## Install, short version

1. Download every file from the [latest release](https://github.com/apedonkey/tribexr-mod/releases) into one folder.
2. Put the headset in Developer Mode and connect it by USB, then run `scripts/install_tribemod.sh <folder>`. Signing the APK with Tribe's own release key first is recommended: see "Choose the signing key" in the guide.
3. In the headset, launch Tribe and tap **OPEN APP**. If the dialog only offers Restore and Close, tap Close and launch again; never tap Restore. Then stand still with straight arms for a second.

## What's where

| Path | What it is |
| --- | --- |
| `hook/` | The mod's source: `dumper.cpp` and the files it includes |
| `scripts/` | The installer, packaging and signing, the character tools and the reverse-engineering tools |
| `stages/` | A snapshot of the stage, light-show, song-analysis and VJ-loop generators |
| `tests/` | Tests for the walking rules, the gait and the intro ride |
| `NOTES.md` | The lab notebook, session by session |
| `claudedocs/` | Plans, notes and concept renders for each stage |

A personal project, shared privately with the Tribe XR team in October 2026. It is not affiliated with Tribe XR or Meta.
