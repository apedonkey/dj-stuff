# Club venue plan: REACTOR (an indoor club for Tribe XR, built to pitch)

Written 2026-10-07, planning only; nothing is built yet. Source brief: `claudedocs/club_venue_prompt.md`. The plan copies the
Halloween plan's method (`claudedocs/halloween_stage_plan.md`), not its files.

**Labels used below:**
- **read**: taken from the mod's object dumps (`logs/scan_final/objects_v7.txt`) or from strings in Tribe's
  `libUnreal.so` (`out/alllibs/`). These are names only, not behaviour.
- **measured**: from a log or a file in this project.
- **Dino**: what the Dino Stage does today.
- **estimate**: my number, to be checked.
- **assumed**: not verified; the check is named.

The Dino session owns `hook/dumper.cpp`, `NOTES.md` and the Dino scripts, and the Halloween session owns its own files.
Section 9 covers how this work stays out of their way.

**Concept renders (2026-10-07):**
- `claudedocs/club_concept/` holds six EEVEE blockout views (stream, crowd, dj_view, gate, aerial, bar), a contact
  sheet, and `club_concept_gate_states.jpg` (the airlock closed/red and open/green).
- They come from `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\club\concept_blockout.py`: boxes and tubes at this
  plan's layout, about 5 s to build and render.
- They show layout, scale, palette and density at a mid-drop moment with everything on. The real build is baked and
  show-lit, so between hits it drops to near black.
- **The user approved the direction on 2026-10-08:** "wow I really like that!!". Phase 1 started.

---

## 0. Decisions (the user, 2026-10-07)

| topic | decision |
|---|---|
| Theme and name | **REACTOR**: a decommissioned reactor hall turned bass club |
| Size | Medium hall, 24 x 36 m, 11 m high (about 120 avatars on the floor at VR spacing) |
| Stage and gate | End stage across the far wall, 1.2 m high, crowd barrier along its front. One staircase at the side is the only way up, with the gate (a containment airlock) at its foot. A backstage door on the other side. |
| Light rig | Full club rig: trusses of moving heads, laser bars, LED pixel strips and tiles, haze |
| DJ role | Tribe's own role. Guests request, the host invites or approves, and the gate opens for whoever Tribe marks DJ, plus the host. |
| Platform | Tribe pitch first. VRChat only if the pitch stalls; the Blender sources stay engine-neutral. |
| First playable must have | thumbstick walking, the gate prototype, a decorative crowd, side screens that mirror the visuals |
| Timing | Runs in parallel, but Halloween comes first until 2026-10-31: it gets first call on the GPU, the headset test slots and the hook |

Working names in code and paths stay neutral ("Club"), so a rename later costs nothing:
- Blender folder `Scripts\Blender\club\`, plus `build_club.py` and `club_materials.py`;
- content under `/Game/Mods/Club/`, map `Environment_Club`, pak chunk 55;
- env box line `Reactor=/Game/Mods/Club/Maps/Environment_Club`.

---

## 1. What Tribe already has (read on 2026-10-07; behaviour not yet verified)

### 1.1 Rooms, hosts and a DJ role
- **Per-player DJ role.** `TribePlayerState` has `GetStagingState`, `SetStagingState` and `OnRep_StagingState`, plus an
  `OnStagingStateChanged` delegate. The enum `ETribePlayerStagingState` has four values: **Spectating, RequestedDJ,
  InvitedDJ, DJ** (read from libUnreal.so strings). An OnRep function means the state is replicated, so every headset
  knows who is DJ.
- **Host.** `ETribeSessionState` is None, PendingHost, **Host**, PendingJoin, Client or PendingLeave.
  `TribePlayerControllerBP_C.IsHost` and `TribePawnBP_C.IsHost` also exist.
- **Moderation.** `TribeGameMode.KickPlayer` and `BanPlayer`; `TribeAccountsManager.IsBannedFromRooms` and
  `IsBannedFromVoice`; mute state per player.
- **Rooms.** `TribeRoom` has GetHostName, GetMaxPlayers, GetNumPlayers, GetNumOpenSlots and GetJoinability.
  Joinability is Public, Featured, OpenToFriends, InviteOnly or Private. Room creation (`W_RoomOptions`) has Max
  Players, Privacy and Genre dropdowns.
- **Environment choice is host-only and replicated.** BP_EnvironmentSkin_C checks IsHost, then
  TribeGameState.SetEnvironment runs (NOTES Session 3l). So an official REACTOR would be picked by the host and loaded
  by everyone in the room.
- **Video calls have their own stage model** (Agora, used for lounges and workshops):
  - `ETribeVideoCallUserPriority`: OnStage, InCrowd, Spectator;
  - `ETribeVideoCallStagingMode`: Open, Queue, QueueClosed, Closed;
  - raise-hand, PromoteUserToStage, MoveToAudience, and a stage-queue timer.
  - This is a second, related system; the club binds to the room role above, not to this one.
- **Not known yet** (probe P1, section 5.7):
  - which transitions the host controls;
  - whether only the host can make someone DJ;
  - whether becoming DJ teleports the player to the decks;
  - how several DJs share the decks.

**What this means for the pitch:** Tribe doesn't need a new role system. The ask shrinks to three things: a gate
that opens for `DJ` and the host, walking, and stage enforcement on the server.

### 1.2 Inputs: the thumbsticks are already bound
`TribePawnBP_C` binds every controller input (read):
- axis events: L and R `Thumbstick_X` / `Thumbstick_Y`, grip, trigger;
- actions: L and R `Thumbstick` (click), `Scroll Up` / `Scroll Down`, `Button 1/2`, `Grip`, `Trigger`, `System`;
- helper functions: `Input_ThumbStickX_Axis`, `Input_ThumbStickY_Axis`, `Input_ThumbStick_Pressed`,
  `Input_Thumbstick_Released`.

**The user (2026-10-08): "the thumbstick in tribe do nothing at all."** So walking can use both sticks. The bindings exist but
do nothing visible; probe P2 still confirms the axis events reach ProcessEvent.

### 1.3 Spawn points, room size, visibility
- **Spawn points** (measured, Session 3t):
  - `PlayerStartDJ` at (-6, 87, 1) cm, facing -Y;
  - `PlayerStartTeacher` at (-6, -58, 1) cm, facing +Y, which is 58 cm in front of the booth, i.e. on our stage;
  - a `PlayerStartSpectator` exists in CommonLevel, position not yet read.
  - **Room guests appear in front of the decks** (the user, 2026-10-08). In REACTOR that is on the stage, inside the
    gate, so the official version needs guest spawns on the dance floor (spec, section 10).
- **Room cap: 16.** The user believes 16 is the largest Max Players option (2026-10-08). Rooms are open (anyone joins)
  or invite-only. A full room is 16 people in a hall built for ~120, so the decorative crowd is essential.
  Tribe does not publish the cap. Its 2026 "What's new" post (tribexr.com/posts/whats-new-2026, dated
  2026-06-24) mentions rooms, video calls, moderation and the Privacy Bubble, but no cap. Probe P4 calls
  `TribeGameInstance.GetTribeSessionMaxPlayers`.
- **Visibility today:** other players see stock Tribe, not our level (the user tested this).

---

## 2. Concept and art direction

**One line.** A bass club inside a decommissioned reactor hall. The DJ plays in front of the core, and the giant screen
is the core's viewing window. Lasers and moving heads cut through the steam. The only way onto the stage is a
containment airlock that opens for DJs.

**Why a reactor works:**
- **The gate has a reason to exist.** "Containment: authorised personnel" is the most natural gate a venue can have.
- **The screen doubles as the core's window.** Tribe hides the backdrop mesh while its visuals are off (Dino:
  the moon behind the screen shows then). Behind our screen sits the glowing core, so the stage never goes blank.
- **It is cheap to model.** Industrial geometry is boxes, tubes, gratings and pipes, which the kit already makes.
  Steam is the haze, and the trusses are the rig.

**Palette:**

| colour | RGB | role |
|---|---|---|
| Cherenkov blue | (0.10, 0.45, 1.0) | carries the look: the core, LED lines, pipe bands |
| Hazard amber | (1.0, 0.55, 0.05) | carries the look: stripes, heads, the bar |
| Alarm red | (1.0, 0.06, 0.03) | accent: beacons, the closed gate, the blackout bar |
| Laser green | (0.15, 1.0, 0.25) | accent: lasers only |
| Steel white | (0.75, 0.85, 1.0) | accent: dimmed, for wash and heads |

Not used, so REACTOR never looks like Halloween or Dino: purple, magenta, and the pure cyan Dino relies on.

**Darkness.** The Dino night rule applies: everything is dark except the DJ, the visuals, the lasers and the lights.
- The hall is unlit and baked, lit by the wash row between hits.
- The full club rig puts more light on the room at drops than Dino does. That light swells over at least 3 frames and
  never flashes.

**Comfort** (the user's rules, unchanged):
- no strobes;
- at most 3 flashes per second anywhere;
- no one-frame hits and no full-frame white;
- on-beat brightness at most ~1.6 x mid-beat.

Blinders and the alarm beacons are slow swells. The beacons rotate at most once per 2 beats.

**Name.** REACTOR, on the LED signs (kit's 5x7 font, 7 characters) and the env box. It can change at any time.

**Mood by set section:**

| section | stage and core | room | rig |
|---|---|---|---|
| intro | core glows dim blue; screen on | pipes and LED lines faint blue | 4 heads, slow amber |
| build | core brightens toward the drop | hazard lines pulse with the beat (soft) | heads come up, the first laser fan |
| blackout bar | only the red beacons and the core | dark | off |
| drop | everything | blue/amber wash on the walls | all heads, laser bars, pixel chase |
| breakdown | core alone, steam | dark | 2 heads, one slow laser |
| outro | fans alternate | fading | heads sweep out |

---

## 3. Layout and fixed constraints

**Frame.** The same frame as the Dino generator: meters, Z up, the DJ at the origin facing -Y, the crowd toward -Y.
- The stage deck is Tribe's floor (z = 0). The dance floor is FLOOR_Z = -1.2, so the stage is 1.2 m high.
- FBX export mirrors Y, which the UE import undoes with a 180 degree turn (measured, Session 3s).

**Fixed by Tribe (measured, Sessions 3t and 3v; meters):**

| thing | value | consequence |
|---|---|---|
| DJ rig, booth table | rig at (-0.05, 0.31, 0.78); table x -0.95..0.85, y -0.05..0.5, top 0.74 | our console front fits the Dino TABLE dimensions |
| SpectatorBoundingBox | x -2.5..2.5, y -2.21..2.79, z -0.06..4.94 | no set geometry inside it except the deck floor |
| SpectatorCamera1 | (-0.02, -0.86, 1.76), looking +Y | the "front" stream shot: DJ, screen and core behind; compose for it |
| BP_MiniMenu | (-0.05, -0.06, 0.93), box x -0.73..0.65, z 0.89..1.91 | nothing inside that box |
| Collision | every StaticMeshActor gets NoCollision (Session 3q) | walls and the gate are enforced by the mod, not by Unreal (section 5) |
| Visuals screen | Tribe's back-wall UV0; the mod finds the mesh by the name `SM_DinoVisualScreen` | our screen asset uses that name in its own package |

**Room** (a proposal; the concept blockout tests it):

| part | extent (x, y in m; z = top surface) |
|---|---|
| Hall interior | x -12..12, y -30.5..5.5. Floor z -1.2; ceiling z 9.8 (11 m above the floor). |
| Core bay | x -12..12, y 5.5..13, ceiling z 12.8. It holds the reactor vessel (r 3.2 m, axis at x 0, y 9.4) behind the screen. |
| Main screen (keywall) | 16 x 9 m (16:9) at y 5.4, x -8..8, z 0.5..9.5 |
| Stage deck | x -8..8, y -3..5.4, z 0. Lip LED strip at y -3. |
| Crowd barrier | y -3.6, x -8..8, 1.1 m high |
| Left wing | x -12..-8, y -3..5.5, z 0. The top of the stairs, then a door to the stage. |
| Airlock (the gate) | A vestibule x -12..-8, y -5.6..-3. It holds the stairs (7 steps x 17 cm, 2.1 m run, rising toward +Y). The door is 2.2 m wide on its -Y face, facing the floor. A red/green beacon and a "CONTAINMENT - DJs ONLY" sign sit above it. |
| Right wing | x 8..12, y -3..5.5, z 0. Backstage door ("CONTROL ROOM") to a short corridor. |
| Side screens | two 16:9 screens, 6 x 3.375 m, on the wings at x +-10, y about +1.5, angled ~35 degrees toward the floor, bottom at z 2.0 |
| Dance floor | x -8..8, y -18..-3.6 (16 x 14.4 m = 230 m2). At ~2 m2 per avatar that is about 115 people (estimate). |
| Mezzanines (raised side areas) | x +-(8..12), y -24..-8, deck z 2.3 (3.5 m above the floor), pipe railings |
| Mezzanine stairs | along the side walls, y -30..-24 (20 steps) |
| Lounge | booths under the mezzanines (3.5 m clearance), standing tables on the back floor, y -24..-18 |
| Bar | counter along the back wall, x -7..3, y -27.5; back bar at y -30.5. Its signs read REACTOR and COOLANT (the user dropped the word BAR, 2026-10-08) |
| Entrance | back wall, x 5..8; a short decontamination corridor outside |
| Rig trusses | 4 across the hall at y -6, -12, -18 and -24, z 8.6; one front-of-stage truss at y -1.5, z 8.8; one core-bay truss at y 3, z 10.5 |

**Top-down sketch** (meters, not to scale; +Y at the top, behind the DJ):

```
 y=+13  . . . . . . . . . . [ CORE BAY: reactor vessel, z to 12.8 ] . . . . . . . . . .
 y=+5.4 |      [=========== MAIN SCREEN 16 x 9 m (the core window) ===========]      |
        | L wing | side screen                               side screen | R wing  |
        | stairs |                STAGE z=0      [DJ]                    | backstage|
 y=-3   | top    |=============== stage lip, LED strip ===================| door     |
 y=-3.6 |  AIRLOCK  ~~~~~~~~~~~~~~ crowd barrier ~~~~~~~~~~~~~~~~~~~~~~~~ |          |
 y=-5.6 | [GATE]   |                                                     |          |
 y=-8   | MEZZ     |              DANCE FLOOR z=-1.2                     |   MEZZ   |
        | z=2.3    |                16 x 14.4 m                          |   z=2.3  |
 y=-18  | lounge   |                                                     |  lounge  |
        | below    |          back floor, standing tables                |  below   |
 y=-24  |----------+-----------------------------------------------------+----------|
        | stairs   |  [ COOLANT BAR  x -7..3 ]           [ENTRANCE x 5..8]  stairs |
 y=-30.5+--------------------------------------------------------------------------+
         x=-12     x=-8                                             x=8         x=12
```

---

## 4. The set, piece by piece

The generator is `club_stage.py`, which adapts `dino_stage.py`'s orchestration: build, bake, export one FBX per
surface, write a manifest.
- Baked with Cycles like Dino.
- **v1 (phase 1, decided 2026-10-08)** ships on Tribe's own unlit instances, the way the Dino Stage started: a static
  night room with frozen beams and lasers. It is the fastest way to judge scale, darkness and the screen in the
  headset.
- The fork-cooked animated materials (show_lit, beams on cue rows, laser_sweep, the VAT crowd) replace them in
  phase 3. The cooking project is already the fork's.
- Tris are estimates. The budget is in Appendix A. v1 measured about 22k tris in all, with no crowd and no haze.

### 4.1 Hall shell (SM_ClubHall, ~30k tris)
- **Walls:** concrete panels in 6 m bays between steel columns.
- **Ceiling:** a ribbed steel deck.
- **Floor:** sealed concrete with painted hazard lines and floor drains.
- **Blue LED lines** run along the column caps and the ceiling ribs (the "architecture lines" row).
- **Details:** stencils ("HALL B", "COOLANT LOOP 2"), warning placards, and pipes along the walls with blue glow bands.
- Cut if late: the stencils and the drains.

### 4.2 Core bay and the reactor (SM_ClubCore, ~15k tris)
- A cylindrical vessel stands behind the screen: r 3.2 m, axis at y 9.4, so its front clears the screen at y 5.4. It
  has a domed head (top at z 12.2). Its glow cells are blue fuel-rod rings, on the "core" cue row, and a soft
  translucent aura surrounds the dome.
- The dome rises above the screen's top edge, so the core is visible from the floor even while visuals play. From
  mid-floor, everything above z ~10.7 shows; this was checked in the blockout.
- Nothing may hang between the floor and the dome. A sign under the front truss hid it in the blockout.
- With visuals off, the hidden screen opens the full view into the core.
- Two control-rod drive towers flank the vessel.
- Cut if late: the drive towers.

### 4.3 Stage, booth and wings (SM_ClubStage, ~12k tris)
- **Deck:** steel plate with hazard edges, and an LED strip on the lip.
- **Booth front:** a reactor control console at the Dino TABLE dimensions, with switch-panel glow and gauges. Like
  Dino, a static booth top only fits the current table height.
- **Two "control rod" light columns** at x = +-3, outside the spectator box, with rising light bars on the build row.
- **Deck lamps:** two small spots on the decks, like Dino's DECK_LAMPS (3 cd, cones 38/20 degrees, no shadows).
  `lights.txt` can scale them by name.
- **The name (REACTOR)** is an LED plate on the core window's top bar, plus the sign over the bar.
  - A sign on the proscenium header is invisible from the floor: it sits above the hall ceiling's sight line.
  - A sign hung under the front truss hides the dome.
  - The blockout tested all three positions.
- **Hall columns:** none on the airlock side at y -6 and -3. They stood in front of the gate; the airlock frame
  carries that bay.

### 4.4 The airlock (SM_ClubAirlock, SM_ClubAirlockDoor, ~4k tris)
- A containment frame with hazard stripes around a 2.2 x 2.6 m doorway.
- **Two sliding door panels**, moved through WPO by the MPC parameter `GateOpen` (0..1).
- **A rotating beacon** on top, red or green by `GateState`.
- **An LED sign:** "CONTAINMENT - DJs ONLY" when closed, "ACCESS GRANTED" when open.
- **A message panel** at eye height that lights only while someone is being refused: "STAGE ACCESS: DJ ONLY".
- Glass side panels close the vestibule, so the stairs can only be reached through the door.
- A low fence joins the airlock to the crowd barrier.

### 4.5 Mezzanines and lounge (SM_ClubMezz, ~20k tris)
- Steel grating decks with pipe railings at 1.1 m, and pipes with blue bands on the fascia.
- LED pixel strips on the fascia edge.
- Lounge booths and low tables underneath.
- Cut if late: the lounge furniture.

### 4.6 Bar and entrance (SM_ClubBar, ~10k tris)
- **The bar:** a counter with a glowing front of blue liquid tubes. Back-bar shelves of glowing bottles (a glow
  palette strip, no text), stools, and a REACTOR LED sign above it facing the stage.
- **The entrance:** a door frame with a decontamination corridor of UV-blue strip lights, about 4 m deep, then black.

### 4.7 Rig (SM_ClubRig, SM_ClubLenses, SM_ClubBeams, SM_ClubLasers; ~30k tris + quads)
- **Moving heads (about 38):**
  - 6 on each of the four hall trusses;
  - 8 on the core-bay truss;
  - 6 floor heads on the deck in front of the screen.
  - They follow the Dino STAGE_AIMS / STAGE_ANGLES / STAGE_COLORS contract, so the baked heads and the show's beams agree.
- **Laser bars (12 sources):**
  - 6 on the front-of-stage truss;
  - 2 at each front end of the mezzanine rails (4), as side crossfire;
  - 2 on the back wall above the bar, aimed at the stage over head height.
  - They sweep through WPO (Dino's laser_sweep, UV1-4 contract).
- **Pixel strips:** the bottom chord of every truss, the mezzanine fascia, the stage lip, and the airlock frame. They
  use Dino's chase material, on the cue table.
- **Pixel tiles:** an LED fascia of 40 x 3 tiles across the stage front, under the lip. It runs a chase and the pulse
  row, not video. (Columns flanking the screen were dropped: the side screens cover them from the floor.)
- **Haze:** two translucent sheets over the floor (z -1.2 + 2.4 and + 5.0), plus beam cones and halos as in Dino.
- **Indoor laser rule:** beams end on surfaces. Each beam's length is clipped to its first hit with the room, and a
  small glow spot sits on the wall there. This is the new `club_lasercheck.py`.
- **Clearances:**
  - no beam within 1.5 m of the DJ's head (estimate);
  - over the floor and the mezzanines, beams stay above head height + 0.5 m (z >= floor + 2.4);
  - nothing crosses the screen.
- Cut if late: the back-wall lasers and the pixel tiles.

### 4.8 Side screens (SM_ClubSideScreen_L / _R)
- Two 16:9 quads with Tribe's back-wall UV0 layout (`visual_screen_uv`), a plain black material and their own names.
- The mod copies the backdrop's live material onto them (section 5.5), so they show the same video.
- Fallback if that fails: they become pixel tiles on the cue table.

### 4.9 Decorative crowd (SM_ClubCrowd, VAT)
- **Source:** crowd v3 (`crowd2/crowd3.py`), imported without edits. It is fully procedural: bodies, rig and dance
  clips are made by the script, and `crowd2/LICENSES.md` lists no third-party assets. So it can go in the pitch bundle.
- **About 200 people:** 150 on the floor, 30 on the mezzanines, 20 at the bar.
- **Lanes are left open:** entrance to bar, bar to floor, and floor to airlock.
- **Tiers:** near and mid only (everyone is within 35 m), about 120k tris (estimate).
- **Knob:** `tribemod/club.txt` takes `crowd=full|half|off`, so real people get room.
- The walking collision treats each dancer as a 0.35 m circle, so the crowd feels solid.

---

## 5. Mod features (`hook/club.cpp`)

### 5.1 Code layout
- All club code goes in a new file, `hook/club.cpp`. `dumper.cpp` includes it (one line) and calls `club_tick()` and
  `club_poll()`, so it can reuse `find_by_path`, `call_uf`, `prop_offset` and the ProcessEvent hook without copying them.
- Everything is inert unless the active environment is the club's map.
- Config: `tribemod/club.txt` (speeds, turn angle, crowd density, role override, debug flags).
- The one include line, the two calls and the MPC lookup change (5.6) are the only edits to `dumper.cpp`. They are
  handed over as a patch script and applied when the Dino session is at a quiet point, with the user's OK.

### 5.2 Walking
- **Input.**
  - Intercept `InpAxisEvt_MotionController L/R Thumbstick_X/Y` in the ProcessEvent hook and read `AxisValue`.
  - Assumed: native input reaches these Blueprint events through ProcessEvent. That is standard UE; probe P2 confirms
    it.
  - While walking, the club swallows the axis events it uses, so Tribe doesn't also act on them.
- **Movement.**
  - Move `TribePawnBP_C.VROrigin` with `K2_SetRelativeLocation`, plus rotation for turning.
  - The giant lift proved this for Z: Tribe never pulls it back, and the avatar's feet follow (measured). X/Y and yaw
    are assumed to behave the same; probe P5.
- **Controls** (defaults, all in club.txt):
  - Left stick walks where you look, at 1.8 m/s, with a 0.25 dead zone.
  - Right stick X snap-turns 30 degrees, re-armed at centre, turning about the head.
  - Holding the right stick click for 1 s sends you **back to the decks**: VROrigin returns to its base pose.
  - A walk-mode toggle (left stick click) is available if Tribe's own stick functions turn out to matter while
    DJing (risk 3).
- **Floors.** The floor height comes from the club's floor map (5.3), eased over 0.2 s on stairs.
- **Later:** a comfort vignette as an option.

### 5.3 Collision and floors (our own, because the set is NoCollision)
- The generator exports `club_collide.txt`:
  - wall segments and boxes with z ranges;
  - walkable floor patches (flat or ramp) for the floor, stage, stairs, mezzanines and wings;
  - the gate box (with an id);
  - the dancer circles.
- The mod reads it at level load and resolves the head position each frame, pushing out and sliding along walls.
  These are 2D checks on a few hundred shapes.
- A preview tool draws the colliders over the top-down render, so every wall is checked before it reaches the headset.

### 5.4 The gate
- **Who is allowed:** you are the session host, or your `StagingState == DJ`. `club.txt` can override the role with
  `auto | guest | dj` to test the refused path.
- **When allowed:** the door slides open when you are within 2 m, the beacon is green, and the sign reads ACCESS
  GRANTED. The door closes 3 s after you pass.
- **When refused:** the door stays shut, the beacon goes red, and the message panel lights. You are pushed back gently,
  by collision rather than a teleport.
- **Already on the stage without the role** (a spawn, a teleport, or a role revoked while up there): you fade out and
  back in at the airlock's floor side within 1 s. The fade is assumed to work through
  `PlayerCameraManager.StartCameraFade`; check it in phase 2.
- **Other players' roles** are readable, because StagingState replicates. A later option: tint their name or a
  floor ring.

### 5.5 Side screens
- After the main screen is registered as the backdrop, read its live material and `SetMaterial(0, ...)` it onto both
  side screens.
- Copy again whenever Tribe changes it (video, GIF, text, NDI).
- `MPC_VideoBackdrop` is global, so the fill mode applies to all three screens.
- Assumed: one material can render on three meshes. That is normal UE behaviour; check it in phase 2.

### 5.6 The show bus
- The club's materials read their own collection, `/Game/Mods/Club/MaterialInstances/MPC_ClubShow`. It has the same
  parameter names as MPC_DinoGiant (ShowLevel, ShowOffset, TopLasers, SpotOn and the rest) plus GateOpen, GateState and
  GateDeny.
- The hook looks up `/Game/Mods/Dino/MaterialInstances/MPC_DinoGiant` by a fixed path (dumper.cpp ~2480).
  Generalising that lookup to the active environment's collection lets song mode, fader-following and beat-grid lock
  drive the club unchanged.
- That is a shared-file change (5.1), and the one the brief asked for.
- Until it lands, the club's show runs free on its 32-bar loop.

### 5.7 Probes (read-only, logged as `[CLUB]`)
- **P1 roles:** every PlayerState's StagingState and name, plus our session state. Logged on change and every 10 s.
- **P2 inputs:** each ProcessEvent call into TribePawnBP_C's input events, with the value (rate-limited). It shows
  what Tribe does with each stick.
- **P3 spawns:** the positions of every PlayerStart actor, our pawn, VROrigin and the HMD.
- **P4 room:** GetTribeSessionMaxPlayers, and the current room's max players, player count and host name.
- **P5 move test:** with `club.txt move_test=1`, shift VROrigin by 1 m in X and turn it 30 degrees for 10 s, then
  restore it. Check that the avatar body, the menus, the pointer, the selfie and drone cameras, and (with a friend)
  what other players see all follow.

The probes ship in the first club APK. P1 and P5 need a friend in the room to give full answers.

---

## 6. The show

- **Cue table.** `club_show.py` writes T_ClubCues in show.py's format: 32 bars x 16 rows, a linear texture; R = level,
  G = strobe (always 0), B = beat pulse.
  - Tempo: 140 BPM half-time, 54.9 s per loop.
  - The laser pattern weights stay on rows 11, 12 and 14, as in Dino, so `laser_sweep` is reused as is.
  - The other rows are the club's:

    | row | carries |
    |---|---|
    | 0 | heads (trusses) |
    | 1 | wash |
    | 2 | core |
    | 3 | stage laser bar |
    | 4-5 | side lasers |
    | 6 | back lasers |
    | 7 | pixel strips |
    | 8 | pixel tiles |
    | 9 | floor heads |
    | 10 | lenses |
    | 13 | always |
    | 15 | beacons |

- **Materials.** `club_materials.py` imports `dino_materials` for the shared factories: cue_level, show_lit,
  beams_material, laser_sweep, chase, scroll_tex and vat_crowd. It adds:
  - `gate_door` (WPO slide);
  - `beacon` (a rotating glow mask);
  - `haze_sheet`;
  - `laser_spot` (the glow where a beam lands);
  - `core_glow`.
  - All of them are fork-cooked.
- **Checks before any push:**
  - `club_cuecheck.py`: flashes per second per row, attack of at least 3 frames, brightest bar against the mid-bar average;
  - `club_lasercheck.py`: beam ends and clearances;
  - `club_overdraw.py`: translucent layers seen from the DJ and from the floor.

---

## 7. Visuals

- **Main screen = the keywall:**
  - named `SM_DinoVisualScreen`, with back-wall UVs;
  - fill mode is set by the existing hook (zero hook change for the main screen).
- **Media:** the Dino VJ pack in `/sdcard/Movies/Dino Visuals/` plays as is.
- **Later, not in the first playable:** a REACTOR loop pack from the Visuals pipeline at 140 half-time, with the same
  gate rules and composed for a 16:9 window.

---

## 8. Technical architecture

### 8.1 File layout

```
C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\club\
  concept_blockout.py   concept renders (task 1; boxes and tubes, EEVEE)
  club_stage.py         the generator (build, bake, export, manifest)
  club_kit.py           `from kit import *`, plus reactor helpers: pipe runs, grating, railings, beacon, hazard
                        stripes, console, vessel. Extends kit's palettes in-process; kit.py is not edited.
  club_show.py          the cue table (tex_cues / write_png_linear reused from show.py)
  club_collide.py       writes club_collide.txt (walls, floors, gate, dancers) and a top-down check image
  checks\               club_lasercheck.py, club_overdraw.py, club_cuecheck.py, club_clearance.py
  out_club\             bakes, FBX, manifest (CLUB_OUT=<dir> for test builds)
C:\Users\Chris\TribeUE\TribeXR\Scripts\build_club.py     UE import: /Game/Mods/Club, chunk 55 PrimaryAssetLabel
                        (build_dino.py's chunk_label() pattern, copied because build_dino runs at import)
C:\Users\Chris\TribeUE\TribeXR\Scripts\club_materials.py
D:\TribeUE\MetaClub\TribeXR   fork-project copy for the club's cooks (C: has 41 GB free, at 96%; D: has 334 GB)
C:\Users\Chris\TribeUE\paks_current\   every current pak, the only input to the OBB (shared with Halloween's plan)
tribe hack\hook\club.cpp                the club's mod code (5.1)
tribe hack\scripts\push_obb.sh          zips paks_current, pushes via /data/local/tmp, mv, md5 (shared)
tribe hack\claudedocs\club_venue_notes.md   this work's running log (NOTES.md belongs to the Dino session)
tribe hack\claudedocs\club_concept\         concept renders and the contact sheet
```

### 8.2 Build and ship (per iteration)
1. **Bake.** `blender -b --factory-startup --python club/club_stage.py`. A full bake is ~20 min by Dino's measure,
   under the GPU lock.
2. **Import.** `UnrealEditor.exe D:\TribeUE\MetaClub\TribeXR\TribeXR.uproject -ExecutePythonScript=build_club.py
   -unattended -nosplash -nullrhi`.
3. **Cook** with the fork:
   - `-map=/Game/Mods/Club/Maps/Environment_Club`. This is a separate project, so the list holds only the club's map.
   - The first cook of a new project compiles the global shaders: 37 min (measured on Meta).
4. **Pack.** `pack_chunk.sh 55` gives pakchunk55-Android_ASTC_P.pak. Copy it into `paks_current\`.
5. **Push.** `push_obb.sh` zips every current pak:
   - 50 and 53 now, and 54 once Halloween ships;
   - 51 and 52 are test chunks (ShaderTest, MetaVat crowd test) and are left out unless asked.
   - Before pushing, check `pidof com.TribeXR.TribeXR` and ask, because a push closes Tribe.
6. **Env box.** Add `Reactor=/Game/Mods/Club/Maps/Environment_Club` to `tribemod/envs.txt` and to
   `backup/tribemod_20261006/envs.txt`, so the re-seed restores it.
7. **Device gate** (logcat `[ENV]`, `[CLUB]`, `[PERF]`):
   - load in 2 s or less;
   - the screen registers;
   - 71-72 fps average outside streaming;
   - the user confirms the pointer and a video on all three screens.

### 8.3 Chunk check
Chunks in use (read from the scripts and paks, 2026-10-07):

| chunk | content |
|---|---|
| 50 | Dino and Festival |
| 51 | ShaderTest |
| 52 | MetaVat crowd test |
| 53 | DinoAnim |
| 54 | reserved for Halloween |
| 55 | free, taken for the club |

---

## 9. Working next to the Dino and Halloween sessions

| shared thing | hazard | rule |
|---|---|---|
| patch OBB on the device | a push that lists only some paks removes the others, silently | `paks_current\` + `push_obb.sh` only. Every session must use it; the user tells the other sessions when it exists. |
| `hook/dumper.cpp` (Dino session, 1,300 uncommitted lines today) | two editors on one file | the club writes only `hook/club.cpp`; the integration patch (5.1, 5.6) is applied once, with the user's OK, at a quiet point |
| APK installs | every `install -r` closes Tribe and can end the Meta token | club hook features ride in a combined APK. Halloween's plan freezes the APK around Oct 26, so the club's features go into that build with everyone's OK, or wait until after Oct 31. |
| GPU (1660S) | bakes and renders collide | `gpu.lock.d`. Halloween has priority until Oct 31; club bakes run when Halloween isn't baking. |
| headset and tester | every device gate needs the user | at most one club device test per day before Oct 31, batched with a written pass/fail list |
| tribemod/envs.txt, reseed ENVBK | a re-seed restores a stale list | append our line in both places, never rewrite |
| NOTES.md | concurrent edits | the club logs to `claudedocs/club_venue_notes.md` |
| Dino files (kit.py, show.py, crowd3.py, dino_materials.py, build_dino.py) | contract drift | import only; start-up assertions name what changed; adapt on our side |
| Halloween files (halloween/, build_halloween.py, hw_materials.py, MetaHw) | none if untouched | never edited |

---

## 10. What we can prototype now, and what Tribe must build

| feature | prototype on the user's headset (mod) | needs Tribe (the spec) |
|---|---|---|
| The venue | the full level from pak chunk 55, loaded through the mod's env box | an official environment: everyone in the room loads it when the host picks it |
| Lights, lasers, song sync | the cue show, song mode, fader-following and beat-grid lock (after 5.6) | optional: Tribe's own show system, or our materials as shipped |
| Walking | yours only: sticks, snap turn, back to the decks, floors, collision | locomotion for everyone, replicated, with comfort options |
| The gate | it stops you, opens for host or DJ by the real StagingState, refuses you in guest mode | the same gate actor, plus server checks: a non-DJ found on the stage is moved to the floor |
| Roles | read only: the real role from Tribe | already there (StagingState). New: "Request access" at the gate starts RequestedDJ; "Revoke DJ" moves the player off stage. |
| Spawns | n/a | room guests spawn on the dance floor; promoted DJs go to the decks |
| Side screens | material copy (5.5) | a supported multi-screen backdrop |
| Decorative crowd | VAT dancers, density knob | density that scales down as real people join |
| What others see | stock Tribe, not the club (tested by the user) | the whole point of the pitch |

**Optional experiment (phase 4):** the stock-slot share.
- Pack the club as a replacement for one stock environment level. Friends copy one patch OBB file and run genuine
  Tribe, and everyone sees the club (without the mod's extras).
- Untested on two counts: genuine Tribe mounting the patch OBB (assumed, because mounting is engine behaviour), and
  everyone staying in the same environment.
- It needs friends with a PC and adb. It would give the pitch a real multi-person video.

---

## 11. Phases, gates and schedule

Halloween wins every conflict until Oct 31, and dates are targets. Each phase ends in something that works.

| phase | target | work | gate |
|---|---|---|---|
| 0 Plan + concept | Oct 7-8 | this plan, the concept blockout (6 views + contact sheet), the notes file | the user approves the direction |
| 1 Scaffold + room v1 | Oct 8-14 | MetaClub on D:, chunk 55 label, paks_current + push_obb.sh (with the user's OK), club_stage.py v1 (hall, core, stage, airlock, mezzanines, bar, screen, side screens, static rig), first bake, build_club.py, first cook (37 min), push | loads in 2 s or less, pointer works, video on the main screen, 71+ fps, Dino still loads from the same OBB |
| 2 Mod features | Oct 10-24 (code); install per section 9 | club.cpp: probes P1-P5, walking, collision + floors, gate, side screens, the 5.6 MPC patch; club_collide.py; one combined APK | each probe answers; walking works end to end with no stuck spots (the user walks the whole hall); the gate refuses in guest mode and opens for host; side screens show the video |
| 3 Show + crowd | Oct 15-30 | club_show.py, club_materials.py (fork), lasers ending on surfaces, haze, pixel strips and tiles, beacons, the VAT crowd, the 3 checks | cue check passes; fps 71+ with crowd and haze, 58+ while streaming (Dino's streaming figure); the user's comfort verdict in a drop |
| 4 Pitch | November | a stream in REACTOR → 1-2 min highlight video; the one-pager and the gate/role/locomotion spec; Quest 3 performance numbers (Quest 2 untested unless someone lends one); the clean asset bundle; optional stock-slot share test; optional REACTOR VJ loops | the user approves the package; contact through Tribe's Discord and the Resident DJ program |

---

## 12. Facts from the user (answered 2026-10-08)

1. Thumbsticks: "do nothing at all". Walking takes both sticks.
2. Max Players: "i believe 16 is the largest".
3. Guests appear "in front of the decks": on our stage.
4. Rooms: "you can make an open room and people join or by inv". How someone becomes DJ is still open: a background
   investigation is decoding it offline ("if you have to look, ghidra is available"). The Blueprint names point at a
   staging icon in the room's player list (W_OnlinePlayerListItem.On_StagingImage_MouseButtonDown) and a server request
   (TribePawnBP.Server_RequestDJMode).
5. Still open: should the club's hook features go in a combined APK before Halloween's freeze, or wait until after
   Oct 31? Phase 3 (show + crowd) needs no APK, so it goes first.

---

## 13. Risks, ranked (probability x cost x silence)

1. **OBB clobbering between three sessions.** It is silent: the box stays and the level fails. Mitigation:
   paks_current + push_obb.sh from phase 1, announced to every session.
2. **Moving VROrigin in X/Y and yaw breaks something Tribe anchors to the play space.** Candidates are the menus
   (BP_MiniMenu is world-placed at the booth), body tracking, the selfie and drone cameras, the Privacy Bubble, and
   what others see. Some of these fail silently. Mitigation: probe P5 before building walking on it, and back to the
   decks restores the base pose.
3. **Walking fights Tribe's own stick bindings.** Now unlikely: the user says the sticks do nothing in Tribe. Probe P2
   still checks the axis events, and walking swallows only the axes it uses.
4. **The role semantics are names, not behaviour.** Mitigation: probe P1 with a friend. Until then the mock role in
   club.txt keeps the gate testable.
5. **Side-screen mirroring fails.** For example, Tribe binds the video to the backdrop component in a way a copy
   can't follow. Mitigation: the fallback is pixel tiles on the cue table.
6. **Collision is hand-authored.** A missed wall lets you walk out of the hall (loud). Mitigation: club_collide.py's
   top-down check image, and a full walk-through at the phase-2 gate.
7. **Overdraw and fps from haze, the full rig and the beams.** Silent in previews, loud on device. Mitigation:
   club_overdraw.py budget, 2 haze sheets, the fps gate.
8. **Comfort with a full club rig.** Mitigation: club_cuecheck.py, swells instead of flashes, and the user's verdict.
9. **Meta token loss on APK installs.** Mitigation: one combined install, and the re-seed procedure (with the user's
   OK).
10. **A small room cap empties the hall.** Confirmed: the cap is about 16 (the user). Mitigation: the decorative crowd
    at full density, thinned only where real people stand.
11. **Pitch ownership.** Everything must be original. The crowd is procedural (LICENSES.md), and kit's font is our
    own 5x7 table. Rule: no downloaded textures, fonts, models or sounds.
12. **Quest 2 is untested.** State it plainly in the pitch, with Quest 3 numbers.

---

## 14. Task 1: concept blockout (done 2026-10-07)

`Scripts\Blender\club\concept_blockout.py` builds the plan's layout in boxes and tubes, in the same frame and with the
same camera language as the Halloween blockout. It renders seven EEVEE views (Standard view transform, bloom) under
the GPU lock, about 5 s in all. The contact sheet (`club_concept_sheet.jpg`) and the gate-states pair are assembled
with PIL, all in `claudedocs/club_concept/`.

| view | camera |
|---|---|
| stream | Tribe's front camera: the DJ, the screen, the core above it |
| crowd | head height mid-floor, toward the stage |
| dj_view | from the decks, out over the crowd |
| gate | the airlock, closed and red, from the floor |
| aerial | a cut-away from above, showing the whole layout |
| bar | from the back of the hall, across the floor to the stage |

It shows layout, scale, palette and density, not the final look.

---

## Appendix A. Budgets

| budget | Dino (measured) | REACTOR target | how it is checked |
|---|---|---|---|
| fps | 71-72 at 72 Hz; ~58 while streaming | 71+ average; 58+ while streaming | logcat fps windows |
| tris | about 600k with the 4.4k crowd | 400k or less: hall + set 110k, rig 30k, crowd 120k, the rest headroom | club_stage.py per-mesh log |
| actors (draw calls) | 32-33 | 40 or fewer | build_club.py log |
| translucent overdraw from the DJ | 0.57 layers/px (beams) | 2.5 or less including haze | club_overdraw.py |
| chunk size | 120 MB | 100 MB or less | pack_chunk.sh output |
| load time | 1 s | 2 s or less | `[ENV]` log |
| flashes | 3/s at most, no 1-frame hits | same | club_cuecheck.py |
