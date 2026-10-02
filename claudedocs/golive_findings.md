# Tribe XR "Go Live" on the modded build — findings

**UPDATED 2026-10-02 — the earlier conclusion was WRONG and is corrected below.** We previously concluded the custom
avatar and Tribe's online video (lounge / Go Live) were mutually exclusive and that streaming was impossible on the mod.
In fact the modded build streams to the user's real Twitch channel through Tribe's own Go Live button, with the custom
avatar active, lounges working, and 360-video visuals — all at once (verified live). The real variable was never the
mod; it was the freshness of the Meta platform token on the headset.

Claims are labeled **[observed]** (measured) or **[inferred]** (best explanation, not directly measured).

## What actually gates Tribe's online video

- **[observed]** Tribe's real-time video (lounge / stages / Go Live, via the Agora backend) requires a valid Meta
  platform token. The system auth service (`com.oculus.horizon`) obtains an app-scoped token for Tribe's app id
  (2055718171162796) from `graph.oculus.com/authenticate_application`.
- **[observed]** With a **fresh** token on the device, the modded (re-signed) build streams fine: 0 auth errors, Twitch
  channel genuinely live, lounges connect, 360 visuals load. With a **stale/absent** token it fails with HTTP 400
  code 27 "Unofficial Application — this app has been modified from its original version", retried ~1/sec, and video
  never starts.
- **[observed]** The re-signed app cannot itself REFRESH the token: `authenticate_application` rejects the modified app
  (that is the "Unofficial Application" 400). But it will happily RIDE a valid token that a genuine login already cached
  on the device — until that token expires.
- **[observed]** A **genuine-signed** build authenticates even when **sideloaded** (0 errors), which resolves the old
  cert-vs-install-provenance confound: the gate is the signing identity for *minting/refreshing*, not the install
  source. Genuine signer `CN=Kevin Lowe, O=TribeXR Inc.` (SHA-256 af43cac3…); our re-sign `CN=Tribe Mod, O=Personal`.

## Why the earlier "impossible / mutually exclusive" conclusion was wrong

- The failing A/B tests (Session 3c) were all run with a **stale or absent** token, so every re-signed build failed
  identically and it looked like the signature permanently blocked video. The pristine-re-sign test correctly proved
  our avatar code wasn't the cause — but the remaining failure was a dead token, not a hard incompatibility.
- Once we re-seeded a fresh token (genuine login) and kept it through an in-place `install -r` of the mod, the whole
  official path came back to life with the avatar still active.

## The working model (current)

- The mod runs everything as long as the Meta token is fresh. Maintenance = keep the token fresh.
- **Never `adb uninstall` the mod** — that evicts the token (and wipes the ~1.9GB OBB and the tribemod data). Use
  `adb install -r` for updates; it preserves token + OBB + data (proven).
- A reinstall also resets runtime permissions, so after any re-seed, re-grant storage (READ_EXTERNAL_STORAGE /
  READ_MEDIA_VIDEO) or the 360 videos disappear.
- Recovery when it expires: `scripts/reseed.sh` (genuine login to mint a token → swap the mod back → restore data +
  permissions). Full manual steps in NOTES.md "Session 3e".

## Open question

- **Token lifetime** — how long a seeded token stays valid (hours? days?) is not yet measured. We learn it by how long
  each session keeps working before the ~1/sec auth errors return. That determines whether re-seeding is a rare chore or
  needs automating.

## Not claimed

- That this is officially supported or permanent. It depends on Meta's current token behavior and Tribe's current
  backend; either could change. This is a personal mod on a burner account with accepted ToS risk; no entitlement/DRM is
  circumvented and the stream uses the user's own Twitch channel.
