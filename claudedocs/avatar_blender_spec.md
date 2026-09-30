# Custom Avatar — Blender Export Spec (Tribe XR mod)

How to build a `.glb` that this mod will load and put on your DJ avatar. The contract is the working
reference file **`DefaultAvatar.glb`** (Tribe's own avatar) — match its shape and yours will load.

---

## What the loader needs (the hard requirements)

The mod loads your file through the engine's glTF runtime **by mesh/skin index (0,0)** and lets it build
its own skeleton. For that to work, your `.glb` must have:

1. **Exactly one skinned mesh** = mesh index 0. (Extra meshes are ignored; keep it to one.)
2. **The mesh is skinned to an armature** — every vertex weighted to bones. This is the non-negotiable part:
   an unskinned/static mesh will *not* load as an avatar (the loader errors "Unable to load SkeletalMesh").
3. **One skin** (index 0) whose joints are your bones.
4. **glTF PBR materials** with embedded textures (base color at minimum).
5. Export as **glTF Binary (`.glb`)** so textures are embedded in the one file.

---

## Reference: what `DefaultAvatar.glb` actually contains

| Thing | Value |
|---|---|
| File size | 4.73 MB, glTF 2.0 binary |
| Meshes | 1 — `Wolf3D_Avatar`, 1 primitive |
| Skin | 1 — `AvatarRoot`, **38 joints**, no explicit skeleton root (auto-detected) |
| Root bone | `Hips` |
| Materials | 1 — base color texture + normal map, OPAQUE |
| Images/Textures | 2 / 2 (embedded) |
| Morph targets | 63 ARKit face blend-shapes (optional — for facial expression) |
| Animations | 18 (face) — **not needed**, the mod ignores them |
| Nodes | 40 total |

**Bone list (half-body — 38 bones):**
```
Hips, Spine, Neck, Head, RightEye, LeftEye,
RightHand + 15 finger bones (Index/Middle/Ring/Pinky/Thumb 1-3),
LeftHand  + 15 finger bones
```
Note: it jumps `Spine → Hand` with **no arm bones**, and has **no legs** — that's why it's a "torso + floating
hands" half-body. Full-body avatars add `LeftUpLeg/LeftLeg/LeftFoot` (and right), plus `Shoulder/Arm/ForeArm`.

---

## Blender workflow

1. **Model** the mesh. Keep it Quest-friendly (~10–15k triangles like the reference; under ~50k to be safe).
2. **Armature (skeleton):**
   - Easiest path: keep the RPM/Mixamo-style bone names above. Hand + finger bones matter most (Tribe's hand
     tracking looks for `LeftHand`/`RightHand`). Legs are optional (add them for full body).
   - A single root bone (`Hips`) with the rest parented under it.
3. **Skin the mesh to the armature:** select mesh then armature → `Ctrl+P` → *Armature Deform → With Automatic
   Weights*. Clean up weights so no vertex is unweighted.
4. **Materials:** use the Principled BSDF. Plug a **Base Color** image texture in (a Normal map is a nice-to-have).
   Keep it to **one material** on the mesh to match the reference.
5. **Morphs (optional):** add Shape Keys for facial expressions if you want them; skip otherwise.

### Export settings (File → Export → glTF 2.0)
- **Format:** `glTF Binary (.glb)`
- **Include:** the armature + mesh (Selected Objects if you've selected them)
- **Transform:** `+Y Up` (on)
- **Data → Mesh:** UVs, Normals, Tangents on
- **Data → Material:** Export → *Export* (materials on)
- **Data → Shape Keys:** on only if you made morphs
- **Data → Armature:** *Export Deformation Bones Only* is fine
- **Animation:** off (not needed)

---

## Test it

1. Save as e.g. `myavatar.glb` (in the repo's `skins/` folder).
2. **Check it on the PC first** — this catches the usual Blender export mistakes before you put the headset on:
   ```
   python scripts/check_skin.py skins/myavatar.glb
   ```
   It ends with two verdicts: **LOADS** (will the mod load it at all) and **MOVES WITH YOU** (can body tracking
   drive it). Every FAIL/WARN line says what to fix in Blender.
3. Copy it to the headset and make it the active skin (headset plugged in over USB):
   ```
   python scripts/check_skin.py skins/myavatar.glb --push --activate
   ```
   (It refuses to push a skin that won't load.)
4. Relaunch Tribe.

If it loads with the wrong colors, the material/texture didn't come across — re-check step 4 of the workflow.
If the avatar doesn't appear at all, the mesh probably isn't skinned to the armature (requirement #2).

---

## Moving with you (body tracking)

The mod drives the avatar with the Quest 3's own full-body tracking (Meta Movement SDK): arms, spine, legs and head
follow you. Tribe's tracked hands replace the model's hands (the model's hand bones are hidden).

For a new skin to animate, its armature needs these bone names (the RPM/Mixamo names above):
`Hips, Spine, Spine1, Spine2, Neck, Head, LeftShoulder, LeftArm, LeftForeArm, LeftHand, LeftHandMiddle1,
LeftUpLeg, LeftLeg, LeftFoot, LeftToeBase` plus the `Right…` mirrors, each hanging from the one before it
(`LeftArm` under `LeftShoulder`, `LeftForeArm` under `LeftArm`, …). A Mixamo-style prefix like `mixamorig:` is fine.
`LeftEye`/`RightEye` are optional; with them the mod matches the avatar's eye height to yours. A missing bone just
doesn't animate. The rest pose can be a T-pose or an A-pose. `scripts/check_skin.py` checks all of this.

Half-body avatars (no arm/leg bones, like Tribe's old ReadyPlayerMe ones) still load, but they follow you stiffly.

**One-time calibration (per person, not per skin):** the first time, stand still for about a second with your arms
straight — out to the sides (T) or down at your sides (A). The mod saves your pose as `tribemod/bt_user_calib.txt`
and works out every skin's fit from it, so new skins need no calibration of their own. To redo it (say, someone else
is playing), delete that file or create `tribemod/bt_recalibrate`.

Two copies of the body are drawn: the full one (with head) for the selfie cam and others, and a headless one that only
you see, so the avatar's head never blocks your view.

## Current limitations (honest)

- **Feet aren't planted:** legs follow the tracking, so feet can float or sink a few cm.
- **Hands are Tribe's**, not the model's.
- **Switching skins re-rigs the moving body** (built; in-headset verification pending).
- **One material / one mesh** for now (matches how the loader reads index 0).
