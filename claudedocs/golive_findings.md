# Tribe XR "Go Live" on the modded build — findings

Why Tribe's Go Live / lounge / streaming fail on our custom-avatar build but work on the official one.
Claims are labeled **[observed]** (measured this session) or **[inferred]** (best explanation, not directly measured).

## The builds compared

| | Official | Ours |
|---|---|---|
| Package / version | com.TribeXR.TribeXR 0.12.5.1 (code 2304) | same |
| App code / resources | — | identical (pristine test was signing-only: `cp` → `zipalign` → `apksigner`, no rebuild) |
| Signing cert | `CN=Kevin Lowe, O=TribeXR Inc.` (SHA-256 `af43cac3…`) | `CN=Tribe Mod, O=Personal` |
| Install source | Meta store (`com.oculus.ocms`) | adb sideload |

## What was tested (clean state each time)

| Build | Version | Signature | Install | Meta auth errors | Agora (video) | Go Live / Lounge |
|---|---|---|---|---|---|---|
| Modded (full mod) | 0.12.5.1 | ours | sideload | ~1/sec | never starts | fail |
| Pristine re-signed (no mod code) | 0.12.5.1 | ours | sideload | ~1/sec | never starts | fail |
| Genuine | 0.12.5.1 | Tribe's | **store** | 0 | active | **works** (streamed to Twitch + live.tribexr.com) |
| Genuine sideloaded | 0.12.5.1 | Tribe's | adb | — | — | **not tested** (build didn't start cleanly; likely the unofficial-app dialog) |

## What this establishes

- **[observed]** The avatar/mod code is not the cause: the pristine re-signed build (zero of our code) fails identically to the full mod.
- **[observed]** Version is not the cause: the store ships the same 0.12.5.1.
- **[observed]** Account/service is not the cause: streaming works right now on the same account.
- **[observed]** The genuine store build produces **0** Meta auth errors and reaches Agora (the real-time video engine); both re-signed/sideloaded builds produce ~1/sec `code 190` auth errors and never reach Agora.

## What is NOT yet isolated

- **Certificate vs install provenance.** The working build was genuine-cert **and** store-installed; the failing builds were our-cert **and** sideloaded. Two variables changed together. A genuine *sideloaded* build was not successfully tested, so we cannot yet separate "the signing identity" from "installed outside the store."

## Mechanism (inference, from client disassembly + logs)

- **[observed]** Tribe requests a Meta user access token + user-proof nonce (`ovr_User_GetAccessToken`, `ovr_User_GetUserProof`, `ovr_UserProof_GetNonce` in the binary) and sends `Authorization: Bearer <token>` + nonce to its backend (`mixreality.tribexr.com`; live base `live.tribexr.com`, both hardcoded at init). Streaming video runs over **Agora**.
- **[observed]** On our build, the access-token/`users.get` calls fail with `code 190` (invalid OAuth token). On genuine, they don't.
- **[inferred]** The most likely reason the token is invalid is the changed signing identity (the main registered attribute we altered). `code 190` itself only says "invalid token" — it does not state cert vs app-ID vs other. Meta's server-side registered configuration and validation rules were not directly observed.
- **[inferred]** The user-proof supports server-side **user** verification; it should not be described as attestation that the whole APK is genuine — any app/cert integrity check is a separate mechanism not directly observed here.
- **[observed]** General login (profile, subscription) persists on the broken build because it rides a saved token; **[inferred]** real-time video sessions need a fresh Meta-backed proof per session, which is what fails.

## Fix status

- **[observed/established]** No fix within our current method: modifying the APK forces a new signature, and we cannot reproduce Tribe's signature without its private key.
- **[not claimed]** Universal impossibility. A Tribe-sanctioned customization/signing arrangement, or future device/firmware changes enabling runtime injection into the untouched store app, would change the constraints. Quest 3 has no public root method at time of writing.

## Practical upshot

Within our re-sign-and-sideload approach, the custom avatar and Tribe's online video (lounge / Go Live) are mutually exclusive per install. Switching = reinstalling (modded ↔ store). The only "both" path explored is the modded build's **local** selfie/spectator cam (renders the avatar with no backend) captured via Quest's own system record/cast — but that is the first-person headset view, not Tribe's third-person stream camera. Not yet tested.
