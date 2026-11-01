# Big Dub stage: running notes

The running log for the Big Dub environment. The plan is `claudedocs/bigdub_stage_plan.md`; the concept artefacts are in
`claudedocs/bigdub_concept/`; the geodata lives in `D:\TribeUE\bigdub_geo\`. NOTES.md belongs to the Dino session, so
Big Dub work is logged here.

## 2026-10-09: planning session (the user: "plan out another festival stage ... big dub ... 3 stages ... walk around")

**Inputs.** The official 2026 camp map (`Big-Dub-Camp-MAP-2026_7.13-1-2048x2048.png` on the Desktop: four stage icons
(Pavilion + Hiscore, Stone Circle, Hemlock Hole, New Camp), 16 theme camps, shuttle stops, the creek, PA 26, the main
entrance to Silver Mills Rd / PA 484). The user names three stages: main, pavilion, new camp.

**Geodata fetched (all public; details and licences in the plan's Appendix B):**
- OSM geocode: Four Quarters Interfaith Sanctuary at 39.7450 N, 78.3688 W (a building on Bridgeport Road).
- USGS 3DEP 1 m DEM tile x72y441 (PA_Northcentral_2019_B19, 342 MB), cropped to 2 x 1.8 km around the farm.
- Esri World Imagery at zoom 17 (whole crop) and 19 (the fields); OSM roads, creek, woods via Overpass.
- Python modules installed for this (user site): tifffile, imagecodecs, pyproj. numpy, PIL and scipy were present.
  Lesson: `python -I` hides user-site packages (PIL "missing"); use `python -P` for scripts that read downloaded data.

**What the data says (the plan's section 1):** the farm is a hillside in a creek bend with 70 m of relief: creek 220 m,
farm buildings 231 m, the central field 242-256 m (8 percent grade), a plateau field at 272-276 m with a 30 m ring
visible in the aerial (the Stone Circle), an upper meadow at 288 m, the ridge road at 278-290 m. The map is north-up and
schematic; read onto the terrain it puts Camp Central and the Pavilion at the top of the plateau field, the Stone Circle
Stage by the ring, Main Camp on the central field, Hemlock Hole above the gorge, the Rainbow Bridge over the west creek,
New Camp on the west bank strip, RV Land on the south bottomland, the camp offices at the Silver Mills Road gate.

**Artefacts made:**
- `D:\TribeUE\bigdub_geo\`: dem_crop.npy/json, dem_hillshade.png, aerial mosaics with OSM overlays and a 100 m grid,
  creek_roads_diagram.png, landmark_sheet.jpg, masks.npz (2 m land cover), landmarks.json, site_plan.png/jpg, and the
  scripts that made them.
- `claudedocs/bigdub_concept/`: bigdub_site_plan.jpg (the layout on the aerial), bigdub_terrain_hillshade.png, the
  blockout sheet and four views.
- `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\bigdub\concept_blockout.py` + `run_concept.sh` (GPU lock) +
  `sheet.py`: the EEVEE night blockout on the real terrain (225k-vert terrain at 4 m, 16k trees from the masks, four
  stage boxes with LED walls and laser lines, 3,900 people, tents and campfires, the ring, the bridge, the creek);
  11 s to build and render 8 views. Lessons: EEVEE Next drew the blended beam cones as grey wedges and they cost 60 s
  of render time (dropped; lasers carry the look); the "stream" camera must sit in front of the DJ looking back at the
  wall, not behind the wall.
- `claudedocs/bigdub_stage_plan.md`: the plan.

**Research pass:** two agents (stages; grounds) were started at ~17:40 to document the real stages, the Pavilion, the
Stone Circle, the bridge and the production credits, with a reference-photo index in the session scratchpad
(`bigdub_ref\stages`, `bigdub_ref\grounds`). Their findings go into the plan's Appendix D and patch the tier-B defaults.

**Checked, not changed:** chunk 56 is free; EM_MAX is 4 and the headset menu is full (Dino Stage, Dino Classic, Reactor,
Graveyard Shift); the live OBB is 50 + 53 + 54 + 55 (412 MB, pushed 17:19); the hook's level loader already locates the
load call's Location parameter (zeroed today), which is what the one-level-three-transforms route in the plan relies on;
walking (hook/club.cpp) already keys its collide file on the /Game/Mods/<folder> name.

**GPU lock:** taken and released three times for the blockout (11-85 s each); the club session's bake held it 18:01-18:14.

**Later the same evening: what the guide and the first photos changed (plan sections 1.4, 1.5, 5.6, 5.7, 6, Appendix D).**
- The grounds agent's downloads (still running at the time) included the official 36-page 2026 guide (text extracted
  with pypdf to `guide_2026_text.txt`; `python -I` cannot see user-site packages, use `python -P`; the console needs
  PYTHONIOENCODING=utf-8 for the guide's ligatures), the 2025 map, and frames of a 2026 drone flyover.
- Facts: the Stone Circle is 61 m across with 60+ stones (two-thirds of the ring), on a hilltop; the Main Stage is the
  Stone Circle Stage (it carries the headliners and closes 11 PM-12:15 AM; the Pavilion, called HiScore in the schedule,
  Hemlock Hole and New Camp run to 4 AM); Camp Central = the Coffee Dragons cafe + the upper shower house; the Rainbow
  Bridge is a ~40 m cable-stayed timber footbridge over a calm 25-30 m reach; Hemlock Hole is a wide pool with a
  gravel beach; the hero photo shows the Main Stage among tall tree trunks with LED pillars and laser fans.
- The ring in the plateau field measures 25 m (`ring_zoom.jpg`), so it is the mown Labyrinth, not the Stone Circle; the
  drone frame t084 shows the Labyrinth in a field that matches the plateau field. That contradicts the north-up reading
  of the map (which puts the Labyrinth in Hilltop, east), so the plan now carries two readings (A north-up, the default;
  B quarter-turned) and asks the user to settle it from the site plan (decision 1). A LiDAR local-relief render
  (`dem_local_relief.png`) and a 60 m ring detector found no Stone Circle footprint (bare-earth LiDAR removes stones).
- A cross-session message from tribe-hack-81 about a headset re-seed was answered: this session has not touched the
  headset, APK, OBB or reseed.sh.
- **Late: reading C.** The grounds agent's partial report plus Four Quarters' own Camp Map 2024 and a zoom-19 aerial
  of the creek peninsula (`aerial_z19_peninsula*.jpg` in D:\TribeUE\bigdub_geo) put Camp Central, the Pavilion
  (green roof) and the Stone Circle on the wooded PENINSULA west of the plateau field, Hilltop + Labyrinth on the
  plateau, the Hemlock Hole / Rainbow Bridge at the peninsula's south-east bend, New Camp on the west bank. Plan 1.4
  now carries reading C as the best-supported; the site plan image and blockout still draw reading A (redo in phase 0).
- The session paused on the usage limit and resumed. The grounds agent's full report arrived (saved verbatim as
  `claudedocs/bigdub_research_grounds.md`; its 129 reference files + manifest copied to `D:\TribeUE\bigdub_geo\ref\grounds\`);
  the stages agent died on its session limit with nothing written.
- **Reading D (final).** The grounds report, Four Quarters' Camp Map 2024 and the 0.3 m/px imagery put Camp Central
  (Coffee Dragons, showers, kitchen, dorm) at the north tip of the low TONGUE inside the North Crook hairpin, crop
  (1059, 126) 229 m; the Pavilion beside it (1035, 171); the Stone Circle in the tongue's woods (1186, 356) +/-120 m
  (reading C's "peninsula" was wrong: that is the Old Forest, west of the creek); the Hemlock Hole = the elbow pool
  (1082, 625); the Rainbow Bridge just downstream (1022, 616), White Pines to the neck; Hilltop + Labyrinth +
  Main Parking + RV Land = the pasture; the farmhouse = Camp Office. The plan's sections 1.3, 1.4, 4.2, 4.4, 5.5-5.7,
  6, 13 and Appendix A were rewritten for it; the site plan (`site_plan_v2.py`) and the blockout (`concept_blockout.py`)
  were redrawn and re-rendered (8 views, 8 s); the copies in claudedocs/bigdub_concept/ are current.
- Stage look from the photos (Appendix D.4): the Stone Circle Stage is a forest stage with an LED wall, LED pillars
  out in the crowd, an emblem above the wall, laser fans from several sources, inflatables in the trees; the smaller
  stages use a white projection screen on truss, not an LED wall; the Pavilion is the HiScore lounge inside.
- Terrain budget note: the walkable core grew to 1,450 x 1,490 m (4 x 4 tiles, 480k tris total, 5-6 tiles in view);
  the heightfield at 2 m is 540k cells (1.1 MB binary).

## 2026-10-09 late night: "keep researching" (the user) → the layout pinned, stage research done

- **Second stage-research agent** (the first died on its limit): report + 56 frames + 22 site files in
  `D:\TribeUE\bigdub_geo\ref\stages\`, copied to `claudedocs/bigdub_research_stages.md`, condensed in the plan's D.5.
  Main results: no production vendor is credited anywhere; year-by-year Stone Circle Stage designs 2023-2026 (2023 had
  a painted knotwork serpent facade and a silver sun emblem; 2024-2026 LED pillars out in the crowd, the sun emblem lit,
  jellyfish and spiky-flower inflatables in the trees); the Pavilion's HiScore lounge decor; a small goal-post truss
  stage with an inflatable octopus and jellyfish (Hemlock Hole or New Camp, unconfirmed); the mascot KIKIWAWA; the
  logo; 2025 food vendors; theme-camp lists; stage name history 2014-2026.
- **Four Quarters' Camp Map 2024** read in full (`camp_map_4qf_2x.jpg` + quadrants): it is a freehand schematic (its
  creek runs east from the Hemlock Hole where the real one runs west), so it fixes the ORDER of places, not their shape.
- **The creek traced from the LiDAR** (`flow.py`: priority-flood fill + D8 accumulation on 2 m cells; `creek_path.json`
  = the main stem in downstream order with water elevations; `creek_channel.json`; `flow_acc_ha.npy`). OSM's line was
  up to 150 m off. Real course: north run at y about -50 (just north of the crop), North Crook hairpin (930, 0), middle
  arm SE to the ELBOW (1230, 530), west run to (890, 516), WNW to the apex by PA 26 (304, 438), south, ESE along y
  700-760, SE to (960, 900), south down the gorge, east along the south edge. The DEM's flat-water test marks a
  continuous pool round the elbow from (1232, 416) to (1168, 596) = the Hemlock Hole; its SE bank is a 25 m cliff.
- **Positions pinned** (plan 1.3, 1.4, 4.2, 4.4, 5.x, 6.x, Appendix A rewritten): the Pavilion = the big dark roof on
  the tongue's north shelf (1072, 76), 247 m; the Stone Circle = the forested knoll beside it, (1180, 130) +/-40 m,
  252 m (the agent's first estimate (1186, 356) was on the flat Big Bottom and contradicted "forested hilltop"; a 61 x
  49 m ellipse fits the knoll top with 3-5 m of relief and nowhere else on the tongue); the Main Stage at the circle's
  east end facing west (assumed); Hemlock Hole Stage on the pool's beach side (1140, 570); the bridge across the west
  run at x about 1110 (+/-50 m; hidden under hemlocks in the imagery; the 2026 flyover t=10-22 shows it on a straight
  reach with the pasture beyond the south bank); New Camp Stage on the neck's terrace at the south landing (1060, 650).
- **Video frames**: the 2026 flyover (fK8UQKUKPIM) and the 2014 drone video (R4x28p3pKjw) were downloaded with
  `uvx yt-dlp`, frames extracted with ffmpeg (36 full-res stills + 1 fps segments) into `ref/video/`, the videos deleted.
- **Artefacts refreshed**: `site_plan_v3.jpg` → `claudedocs/bigdub_concept/bigdub_site_plan.jpg`; the blockout
  (`concept_blockout.py`) moved to the new positions with the LiDAR creek and re-rendered (the newcamp and stonecircle
  views come out black from inside the tree cones and were left off the sheet; re-aim in phase 0).
- **Still open / not found**: production vendors; which small stage carries the sea creatures; the bridge's exact
  landings; the Pavilion's roof pitch and post spacing; the Stone Circle's stone-by-stone layout (4qf.org blocks
  downloads); the Main Stage's facing. A cross-session message from the Dino session (tribe-hack-f1) asking whether this
  was the Halloween session was answered: no.
- The stage agent's final messages (02:33) repeat report.md (unchanged, 17,237 bytes). Its one on-disk follow-up was
  taken: the 2026 theme-days poster reads Thursday Pajama Jam, Friday Under the Sea, Saturday Spaced Out Saturday
  (plan D.5): the Friday headliner crowd gets an under-the-sea costume layer. Its other suggestions (the 2022
  aftermovie nLbX0CxYh2w and the 2019 "Big Dub X" recap GRu5LyCUkPI for the 2019-2022 stage looks; asking the festival
  for its production vendor) are left for phase 2.

## 2026-10-10 - daylight renders for the phone

The user looked at the night blockout on mobile and could not see anything in it. Added to
`Scripts\Blender\bigdub\concept_blockout.py`:

- `--day`: sun (3.5 W/m2, 45 deg up from the south-west) + sky world, AgX view transform, daytime palettes for the
  ground classes, trees, tents, RVs and crowd, no glow on ground/crowd/tents, campfires off. Night mode is unchanged.
- Stage clearings: `in_clearing()` keeps trees out of the Stone Circle ellipse (+18 m) and out of every stage's crowd
  fan (14 m behind the booth to deck + spread depth + 8 m, half-width + 8 m). masks.npz calls the whole tongue woods
  (Camp Central 76 percent, Big Bottom 67, Stone Circle box 85), so without this the stages vanished under the canopy.
  The plan already assumed cleared crowd fields (section 5 camps table, "the crowd field in front of the Main Stage
  stays clear"); this makes the blockout match it.
- Bug fixed: the Stone Circle's open third faced north (t = -30..210 deg); the stage stands at the east end, so the
  stones ran through the LED wall. Now t = 60..300 deg, opening centred on east (then the -12 deg ring rotation).
- Cameras: `core_top` (720 m over (1140, 330): the tongue, the elbow, both creek runs), `aerial_main` (low oblique
  from the Big Bottom onto the knoll), `main_side` (over the crowd's left shoulder: stage, stones, crowd, parking);
  `stonecircle` moved inside the ring at (1160, 140); `aerial_top` raised to 1550 m over (1050, 680).
- Labels: each render writes `labels_<view>.json` (world_to_camera_view of the stages, places and camp centres);
  `annotate.py <dir> views...` draws them with PIL (Arial Bold, black stroke) and writes the JPGs. Ground views keep
  only labels within 220 m plus stages within 400 m; crowded labels are dropped rather than cascaded.

Outputs: `Scripts\Blender\bigdub\concept_day\` (12 views) copied to `claudedocs/bigdub_concept/day/`; the night set
re-rendered with the same geometry fixes into `claudedocs/bigdub_concept/` (sheet now aerial, aerial_top, main_side,
main_crowd, pavilion, hemlock). Sent to the user's phone: main_side, main_crowd, aerial_main, pavilion, hemlock,
newcamp, core_top, aerial_top, aerial.

Things the daylight pass made visible (for the user's layout check, plan section 13 decision 1):
- The Hemlock Hole Stage and the New Camp Stage are only ~115 m apart across the west run; from the New Camp camera
  both stages sit in one frame. If the real New Camp Stage is further west (the Great Meadow side), that gap grows.
- The main-stage crowd fan (90 x 120 m for 2000 people) spills well outside the 61 x 49 m ring, west over the slope
  toward Camp Central and onto the Village Green parking strip; the real event is likely denser inside the ring.
- Village Green parking (RVs) sits 20-40 m from the Main Stage's left wing in the blockout; the plan's parking rect
  (1150-1280, 50-100) may be too close for a real stage build.
- Follow-up: crowd placement no longer skips woods cells (the fan is cleared now), only water; before this the 2000
  people clumped on the mask's few field cells and read as blobs. Night set and sheet re-rendered with the same rule.
