# Stage sources (snapshot of 2026-10-14)

The scripts that generate the mod's stages, lasers, moving heads, crowds, light scripts and VJ loops. These are copies:
the live versions stay on the modder's PC, outside this repo, and keep changing. The Unreal projects themselves (mod
content, config and plugins of three stage projects and a crowd-test project) are in the GitHub release as
`stage-sources.zip`.

| Path | What it does | Runs in |
| --- | --- | --- |
| `scripts/Blender/dino_stage.py`, `Blender/halloween/hw_stage.py`, `Blender/club/club_stage.py` | Build each stage's geometry and bake its lighting with Cycles; write one FBX per material plus PNG textures | Blender 4.5, headless |
| `scripts/Blender/show.py` | The light show's data textures: the 32-bar cue table, the laser program (8 variants) and the pattern library (60 motion patterns, 16 colour schemes) | Python + numpy |
| `scripts/Blender/grounds/atmosphere.py`, `Blender/club/club_lasers.py`, `Blender/club/club_movers.py`, `Blender/halloween/` | The laser and moving-head fixtures, with each beam's pivot, amplitudes, group and phase written into its UV channels | Blender |
| `scripts/Blender/crowd2/`, `Blender/vat/`, `Blender/halloween/crowd/`, `Blender/club/club_crowd.py` | Procedural crowds, animated with vertex animation textures | Blender |
| `scripts/build_dino.py`, `build_club.py`, `build_halloween.py`, `build_festival.py` | Import a stage into its Unreal project, create its materials and actors, label it into its pak chunk | Meta's UE 5.4.4 fork editor, `-ExecutePythonScript` |
| `scripts/dino_materials.py`, `club_materials.py`, `hw_materials.py` | The materials, including the laser and moving-head motion (Custom HLSL nodes driving World Position Offset) | Meta's fork editor |
| `projects/<project>/` | Cook, pack and OBB scripts from each Unreal project (`cook_*.sh`, `pack_chunk.sh`, `make_obb.py`), plus `verify_fork.sh` | Git Bash |
| `scripts/songs/scan_library.py`, `make_cues.py` | Measure every track in the headset's Music folder and write one light script per track | Python + librosa |
| `scripts/Blender/bigdub/` | Big Dub terrain and blockout (a planned stage) | Blender |
| `visuals/dino/`, `visuals/reactor/`, `visuals/graveyard/` | The VJ loop generators for each pack: a shared kit (`vjkit.py` for the Dino pack) and one script per loop; `assemble_set.py` builds the 60-minute sets; `CONCEPTS.md` describes the Dino and REACTOR packs | Blender 4.5, EEVEE |

Which project builds which stage: `Meta` = Dino Stage (chunk 50) and the Festival test level, `MetaClub` = REACTOR
(chunk 55), `MetaHw` = Graveyard Shift (chunk 54), `MetaVat` = crowd and vertex-animation tests. Dino Classic (chunk 53)
is an older Dino build; its source is not in this snapshot.

Paths inside the scripts point at the modder's PC (`C:\Users\Chris\TribeUE`, `D:\TribeUE`, `D:\MetaUE54` for the fork
engine). Change them before running anything. The guide's "Building it yourself" section explains the order.
