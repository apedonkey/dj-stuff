# Big Dub plan: BIG DUB 2026 at Four Quarters Farm, three stages, walkable

Written 2026-10-09, planning only; nothing is built. The method is the Halloween plan's (`claudedocs/halloween_stage_plan.md`)
and the club plan's (`claudedocs/club_venue_plan.md`): the Dino pipeline for content, the club's walking for locomotion.
The source brief is the user's message of 2026-10-09 and the official 2026 camp map
(`Big-Dub-Camp-MAP-2026_7.13-1-2048x2048.png` on the Desktop).

**Labels used below:**
- **geo**: taken from public geodata fetched today (USGS 1 m LiDAR elevation, Esri aerial imagery, OpenStreetMap). These
  are the ground truth for the land; files in `D:\TribeUE\bigdub_geo\` (Appendix B).
- **map**: read from the official 2026 camp map. It is schematic (stretched, not to scale), so it gives what is where,
  not how far.
- **research**: from the web research pass on the real stages and grounds (Appendix D). Labelled per claim.
- **measured** / **Dino** / **read**: as in the other plans (logs and files in this project; what the Dino Stage does;
  names read from the mod's dumps or the hook source).
- **estimate**: my number, to be checked. **assumed**: not verified; the check is named.

**Concept artefacts (2026-10-09), all in `claudedocs/bigdub_concept/`:**
- `bigdub_site_plan.jpg`: the festival layout drawn on the real aerial, with the elevations. This is the picture to argue
  with: every rectangle and arrow on it is a proposal from the map read onto the terrain.
- `bigdub_terrain_hillshade.png`: the LiDAR terrain with 5 m contours, the creek, the roads, and the one building OSM
  knows (north up, 1 px = 1 m, 2 x 1.8 km).
- `bigdub_concept_sheet.jpg` and four views: an EEVEE night blockout of the real terrain with boxes for stages, tents,
  people and lasers, from `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\bigdub\concept_blockout.py` (11 s to build and
  render under the GPU lock via `run_concept.sh`). It shows scale and slopes, not the look: the stage boxes are
  placeholders until the research photos are worked in (section 6).

---

## 0. The ask, and the assumptions this plan stands on

The user: a third custom environment, "Big Dub" (a real festival, bigdubfestival.com, July 21-26 2026 at Four Quarters
Farm, Artemas PA), with its three stages (main stage, pavilion, new camp stage), "as exact as possible", and walkable
("other chats here have confirmed we can do this": the club's walking, section 7).

| assumption | basis | if wrong |
|---|---|---|
| "Three stages" = the Main Stage, the Pavilion Stage and the New Camp Stage. The 2026 map shows FOUR stage icons: Pavilion Stage + Hiscore, Stone Circle Stage, Hemlock Hole Stage, New Camp Stage | map; the user's words | Hemlock Hole is built as a lighter fourth stage either way (decision 4); if the user's "main stage" is Hemlock Hole rather than Stone Circle, the two site entries in section 6 swap roles, nothing else changes |
| The Main Stage is the Stone Circle Stage | the 2026 guide's set times: it carries the headliners and "Mainstage closes" means the Stone Circle closing (section 1.5) | settled; what is still open is WHERE that stage stands (section 1.4, decision 1) |
| It is a night set, like every stage so far | the user's rule (2026-10-05) | a dusk variant is one sky texture and a bake exposure |
| Tempo 140 BPM half-time for the show and the crowd | the user's sets (memory) | one constant |
| It ships like the others: one pak (chunk 56) in the shared patch OBB, menu boxes in tribemod/envs.txt, the mod loads it | Dino, Halloween, club | none; this is the only route |
| Walking uses the club's locomotion (hook/club.cpp), extended for terrain | club notes 2026-10-08/09: walking works on any stage with a collide file | section 7 lists the exact changes; they are patches to the club session's files |
| The user tests on one Quest 3 and streams with Go Live | Sessions 3h, 3v | re-seed procedure before a stream |
| Scale 1:1 with the real site. Walking from the Main Stage over the bridge to the New Camp Stage takes about 4 minutes at 1.8 m/s; a full lap of the site about 15 | geo: 400 m by the paths; 1.6 km lap | a run speed (section 7) and shuttle-stop fast travel (decision 6) |

---

## 1. The real site, from the data

This is the part that makes "exact" possible. Everything here is **geo** unless marked.

### 1.1 Sources (all public, fetched 2026-10-09, kept in `D:\TribeUE\bigdub_geo\`)
- Position: OpenStreetMap places "Four Quarters Interfaith Sanctuary" (a building) at 39.7450 N, 78.3688 W, Bridgeport
  Road, Mann Township, Bedford County, PA 17211. Everything is measured from there.
- Terrain: USGS 3DEP 1 m LiDAR DEM, tile `USGS_1M_17_x72y441_PA_Northcentral_2019_B19.tif` (342 MB, EPSG:26917 = UTM
  17N, public domain). A 2,000 x 1,800 m crop around the farm is `dem_crop.npy`; 1 px = 1 m.
- Imagery: Esri World Imagery tiles at zoom 17 (0.92 m/px, whole crop) and zoom 19 (0.23 m/px, the farm's fields).
  Reference only; nothing from it ships.
- Roads, creek, woods: OpenStreetMap (Overpass): Sideling Hill Creek, PA 26 (Clear Ridge Road), PA 484 (Buck Valley
  Road), Silver Mills Road, Bridgeport Road (the farm's private road), two more private farm roads, the wood polygons.
- Land cover: `masks.npz`, 2 m cells over the crop, classed field / deciduous woods / evergreen / water / road from the
  imagery plus OSM (texture + colour thresholds; `masks.py`). Good enough to place trees, not a survey.

**The crop frame** (used for every coordinate in this plan): x east, y south, metres; origin = DEM pixel (row 5937,
col 4350) = UTM 17N E 724,344 N 4,404,069. The OSM building sits at (1100, 1300). `landmarks.json` has every landmark
below in crop metres, UTM, lat/lon and elevation.

### 1.2 The terrain in one paragraph
The farm is a hillside inside a bend of Sideling Hill Creek, not a flat field. The creek wraps it on the west (a gorge:
water at 220-227 m, banks climbing 20 m in 50 m) and the south (bottomland at 218-222 m). From the creek the land
climbs north-east: the farm buildings at 231 m, the big central field from 242 m at its west edge to 256 m at its top
(an 8 percent grade, median slope 6 degrees), a plateau field at 272-276 m beyond it, an upper meadow at 288 m, and the
ridge road at 278-290 m. Seventy metres of relief in 600 m. Across the creek to the south-west, PA 26 runs along the
opposite hillside at 270-277 m, 50 m above the water.

### 1.3 Landmarks (crop metres; elevation at the point; what the aerial shows)

Positions follow reading D (section 1.4) as refined late on 2026-10-09 with Four Quarters' own Camp Map 2024
(`ref/grounds/camp_map_4qf_via_earthskillsrevival.jpg`), the creek channel traced from the LiDAR (`creek_path.json`,
a D8 flow trace: OSM's creek line is hand-drawn and up to 150 m off), the 0.23 m/px imagery and the 2026 drone
flyover. Labels: "4qf" = named on Four Quarters' map; "geo" = seen in the imagery or the DEM; "research" = the grounds
agent (Appendix D.3); "inferred" = my reading, with the uncertainty.

**The creek, as the LiDAR has it (geo):** it enters at the NE under the Silver Mills Road bridge, runs WEST along the
site's north edge at y about -50 (just north of the crop; it dips into the crop at x 1140-1220, y 0-50), hairpins at
NORTH CROOK (930, 0), runs SOUTH-EAST down the "middle arm" to the ELBOW at (1230, 530), turns WEST along the "west run"
(y 560-620) to (890, 516), continues WNW to the APEX by PA 26 (304, 438), turns SOUTH, then ESE along y 700-760 to
(960, 900), SOUTH down the GORGE (x 930-970) to (930, 1340), then EAST along the south edge past the farmhouse to the
PA 26 / PA 484 bridge (1998, 1526). Water surface 230 m at the crook, 227 at the elbow, 225 at the apex, 221 in the
gorge, 216 at the outflow. The land it wraps: the TONGUE (Camp Central's loop, 960-1300 x 0-620) with the creek on its
north, south-west and south; the PENINSULA (330-1000 x 400-840, the Old Forest) with the creek on its north, west and
south, joined to the Hilltop pasture by the NECK (960-1150, 620-720); the west bank strip and the slope up to PA 26
beyond the gorge.

| landmark | x, y | elev | notes |
|---|---|---|---|
| North Crook | 930, 0 | 230 water | the hairpin (geo): the North Crook swimming hole, "premier camping by the river", the River Side Fire Circle, the Lower Shower House "at the base of the hill from the Pavilion", a shuttle stop, in-camp parking rows along the creek (4qf, research) |
| Camp Central shelf and buildings | 1020-1150, 50-130 | 244-250 | the tongue's north shelf, 15-20 m above the creek (geo); the big dark-roofed building at (1072, 76), a second roof at (1083, 92) and a shed at (1090, 70) (geo); per the 4qf map's order along the north shore from the crook eastward: Dining Pavilion + Showers, the Starvin' Artist Kitchen, the In-Camp Dormitory, the Cliffside Stage, the Bardic Circle, then Coffee Dragon Hospitality (first aid, camp services, showers, flush toilets) at the north-east; the Fire Circle inside the loop |
| the Pavilion | 1072, 76 | 247 | inferred +/-30 m: the biggest roof on the shelf, 25 x 20 m in plan including an attached wing (the 70 x 30 ft pavilion plus the kitchen's service line), "perched on the hillside above the creek" (4qf); its green standing-seam roof reads dark in the leaf-off imagery |
| Village Green and In-Camp Parking | 1150-1280, 50-100 | 250-253 | an open clearing with a gravel loop on the knoll's north side (geo); the 4qf map puts the Village Green and the In-Camp Parking here, east of the dormitory |
| Stone Circle | 1180, 130 | 250-253 | inferred +/-40 m: the 4qf map puts it south of the Village Green inside the Loop Road; the guide says "a forested hilltop"; the only hilltop on the tongue is this knoll (252-253 m at its top, 2.9-5 m of relief inside a 61 x 49 m ellipse at (1180-1200, 120-140); everywhere else on the tongue is either the bottomland or a 15 percent slope). The research's earlier estimate (1186, 356) is on the flat Big Bottom and is dropped |
| the knoll's slopes | 1100-1250, 140-260 | 230-250 | the "triangle woods": hardwoods on a 10-15 percent slope falling SW from the circle to the bottomland (geo); the natural crowd field below a stage on the knoll |
| the Big Bottom / Members Camp | 960-1250, 200-520 | 229-236 | the flat terrace inside the elbow (geo: 2.2 ha under 4 degrees); Members Camp's tent platforms, Main Camp's tent camping, theme camps (4qf, Big Dub map) |
| High Meadow | 1300-1500, 330-520 | 245-259 | the scrub ridge with small conifers east of the Big Bottom (geo); Ridge Road and "Car Camping" along it, "Cliffs" beyond (4qf); the Big Dub map's High Meadow Camp |
| White Pines | 1040-1200, 520-590 | 227-232 | the tongue's south tip inside the elbow: conifers (geo); EMS, ice, a shuttle stop, White Pines Loop (Big Dub map); the Fox Altar (4qf) |
| Hemlock Hole | 1170-1240, 420-600 | 227 water | the elbow pool (geo: the DEM's flat-water test marks a continuous pool from (1232, 416) round the elbow to (1168, 596)); a gravel beach on the inside of the bend (the tongue's south tip, 227-229 m) and a shale cliff on the outside (the south-east bank climbs from 228 to 254 m in 60 m, geo), hemlocks along the water (research, photos); "spectacular swimming area, shadowed by our cliffs" (4qf) |
| Rainbow Bridge | 1110, 585-640 | deck ~236 | inferred +/-50 m along the run: the 4qf map puts it just downstream of the Hemlock Hole; downstream is west; a suspension footbridge "8-10 m above the water" from the tongue's south tip (north bank, 228 m) to the neck's terrace (south bank, 240 m), 55-65 m between the banks' tops (geo), hidden under the hemlock canopy in the imagery; the 2026 flyover shows it crossing a straight calm reach with camps on the north bank and the pasture beyond the south bank |
| the neck | 960-1150, 620-720 | 236-262 | the slope joining the Old Forest to the pasture, with a 240 m terrace at the bridge's south landing (geo); the 4qf map's "Stage" just south of the bridge |
| the Old Forest | 330-1000, 400-840 | 224-267 | the wooded peninsula wrapped by the west run, the apex and the ESE run (geo); "The Old Forest & Ritual Area", the Wolf Altar, the Oak Spring Altar, the Lower Switchback (4qf); the Old Forest Stage of 2019 = the New Camp Stage; New Camp tent camping |
| Hilltop pasture | 1000-1300, 700-1230 | 230-276 | one mown field rising from the farmhouse to 276 m at its north end (geo): Main Parking, Hilltop Camp, RV camping, the Labyrinth at (1147, 800) (research + geo); the 4qf map's "Farm Fields" |
| stalls row on the bluff | 1066, 659 | 259 | service structures and a row of stalls/hookups at the pasture's north edge above the west run (geo) |
| Loft & Shop | 1282, 986 | 260 | storerooms on the road up the ridge (4qf, research) |
| Farmhouse, Camp Office, Main Registration | 1084, 1281 | 231 | the green-roofed cluster on Walker Lane, with the winery and gardens (4qf); the Main Entrance is 564 m east where Walker Lane meets Silver Mills Road at (1668, 1286) |
| Great Meadow / New Camp | 600-935, 900-1320 | 222-270 | west of the gorge: the west bank strip (880-930, creek-side tents), a mown field at (734, 1036), the Upper and Lower Switchbacks climbing to the West Entrance = New Camp gate on PA 26 at (743, 1251) (4qf, research: observed gate coordinate); the New Camp Sweat Site and the Warriors Altar (4qf) |
| Fairview Station | 568, 1207 | 276 | the parking field west of PA 26 with a green-roofed house (research, flyover) |
| Big Pool and the river foot crossing | 930, 1340 | 219 | the gorge's south bend: a swimming hole and the ford to the Members Village (4qf) |
| Beaver Dam foot crossing | ~950, 560 | 226 | a second crossing of the west run further downstream of the bridge (4qf; position inferred) |
| PA 26 / PA 484 bridge | 1998, 1526 | 216 | the creek's outflow (geo) |

### 1.4 How the map was read onto the terrain
The map is north-up and schematic. Four things pin it: PA 26 runs along the south-west edge on both (**geo**: Clear Ridge
Road is across the creek to the south-west); the creek wraps the top-left and runs down the middle-left on the map and
wraps the west and south in reality; the main entrance points east to Silver Mills Road / PA 484 on both; Fairview
(a church on PA 26, **geo**) is west, where the map puts Fairview Station. With those fixed, the map's areas land as in
the table above and on `bigdub_site_plan.jpg`: Camp Central and the Pavilion at the top of the plateau field, the Stone
Circle Stage by the ring, Main Camp on the central field, Hemlock Hole at its north-west corner above the gorge, the
Rainbow Bridge over the west creek, New Camp on the west bank strip (its own entrance from PA 26, which is why it needs
a footbridge to the rest), RV Land on the south bottomland, the camp offices at the Silver Mills Road gate, Hilltop Camp
on the wooded hillside up to Ridge Road, High Meadow on the upper field.

**Settled on 2026-10-09 by the grounds research, then refined the same night (reading D; Appendix D.3, section 1.3).**
Four Quarters' own Camp Map 2024, its camp-tour text, the 2019 Big Dub map's labels, the LiDAR-traced creek and the
0.23 m/px imagery agree on a layout that none of the three readings drafted earlier that day had: the festival's core
is the TONGUE of land inside the creek's northern loop, wrapped by the creek on its north (the north run), its
south-west (the middle arm) and its south (the west run from the elbow). Camp Central (the Pavilion with the kitchen,
the Upper Shower House, the dormitory, the Cliffside Stage, Coffee Dragons) is the building shelf on the tongue's north
side, 244-250 m, 15-20 m above the creek, with the Pavilion the big dark roof at (1072, 76); the Village Green and
the in-camp parking are the clearing east of it; the Stone Circle is on the forested knoll beside them, centre
(1180, 130) +/-40 m, 252 m, the only hilltop on the tongue (the research's first estimate put it 230 m further south on
the flat Big Bottom, which contradicts the guide's "forested hilltop" and was dropped); the Big Bottom is the flat
229-236 m terrace inside the elbow, Members Camp and Main Camp's tents; High Meadow is the scrub ridge east of it
(1300-1500, 330-520); White Pines is the tongue's south tip at the elbow. The Hemlock Hole is the elbow pool
(1170-1240, 420-600), beach on the tongue side and cliff on the south-east bank; the Rainbow Bridge crosses the west
run just downstream of the pool at about x 1110 (+/-50 m along the run), from the tongue's south tip to the neck;
across it lie the neck's terrace with the New Camp Stage (the 4qf map's "Stage", the 2019 "Old Forest Stage"), the Old
Forest (the wooded peninsula) and, beyond the gorge, New Camp proper (the Great Meadow side: the west bank strip, a
field, the switchbacks up to its own PA 26 gate). Hilltop Camp, Main Parking, RV camping and the Labyrinth are the big
pasture south of the elbow (the plateau field and the central field are one pasture rising from the farmhouse at 231 m
to 276 m at its north end); the farmhouse cluster on Walker Lane is the Camp Office and Main Registration, with the Main
Entrance 564 m east on Silver Mills Road. The Big Dub map is north-up with the tongue stretched to the top-left.
`bigdub_site_plan.jpg` and the blockout were redrawn for this layout; every section below uses it; the three earlier
readings are kept here only as the record of how it was found.

**How it was found (the three readings tried first):** the ring in the plateau field is 25 m across, which is a
labyrinth, not the 61 m Stone Circle, and the drone footage puts the Labyrinth in exactly that field; but the map
draws the Labyrinth in Hilltop Camp, on the far EAST. So the day's readings were:

- **Reading A (the plan's default, used in every section below):** the map is north-up and the plateau field is Camp
  Central + the Stone Circle field, with the Labyrinth simply drawn in the wrong place on a schematic map (the Stone
  Circle itself, 61 m and "upon a forested hilltop", would then stand in the woods beside the plateau; the leaf-off
  aerial shows no 61 m clearing there, and a bare-earth LiDAR removes standing stones, so the data can neither confirm
  nor refute it). For A: "upper shower house near Coffee Dragons" (the guide) fits buildings at 272 m better than
  buildings at 231 m.
- **Reading B:** the map is turned about a quarter turn (map east = real north): the plateau field is HILLTOP CAMP
  (the Labyrinth, RV camping, the big parking, the shuttle stop, which is what the drone frame shows: RVs, a school
  bus, rows of cars), the farm's building cluster at (1090, 1265) is CAMP CENTRAL with the Pavilion (its 25 x 15 m
  green-roofed hall is pavilion-sized), the Stone Circle Stage sits up the slope north-east of it on the central field,
  and the main entrance comes down Bridgeport Road from Silver Mills Road at the north-east. B puts New Camp in the
  wrong place (it must be across a footbridge from Main Camp and reachable from PA 26, which only the west bank strip
  satisfies), so B is not clean either.

- **Reading C (the third attempt that evening, superseded by D within the hour):** Four Quarters' own "Camp Map
  2024" (`camp_map_4qf_via_earthskillsrevival.jpg` in the research folder) and the 0.23 m/px aerial of the creek
  PENINSULA agree: the Stone Circle, the Village Green, the Coffee Dragons cafe, the dining Pavilion (70 x 30 ft, green
  standing-seam roof, built 2010), the dormitory and the upper shower house all stand on the wooded peninsula that the
  creek wraps on three sides WEST of the plateau field, at about crop (500-700, 420-550), elevation 240-265 m; the
  aerial shows a building cluster with a green roof and a parking loop there at (620-660, 480-500). The Hemlock Hole
  and the Rainbow Bridge are at the peninsula's south-east bend near (930, 870), the bridge leading to the west bank
  ("the Great Meadow" with the "Lower Switchback" up to the New Camp entrance on PA 26 at (743, 1251)). The plateau
  field IS Hilltop Camp with the Labyrinth and Main Parking; the central field is "Farm Fields" / RV Land; the farm
  buildings on Walker Lane are the Farmhouse and Camp Office with the main entrance from Silver Mills Road; the Big
  Pool swimming hole and a river foot crossing are at the west arm's south bend (930, 1350). So the Big Dub map is
  north-up with the peninsula stretched to the top-left. The site plan image and the blockout still show reading A and
  must be redrawn for C in phase 0; the landmark table's rows for the plateau and Camp Central change accordingly.

Reading D replaced all three: it is the only one in which the Stone Circle is a forested site (the hero photo's tall
trunks), the Labyrinth is on Hilltop, Camp Central has permanent buildings beside the creek, the bridge spans a pool
next to the Hemlock Hole, and New Camp has its own PA 26 gate.

**The late refinement (2026-10-09, after the grounds report):** Four Quarters' own Camp Map 2024 was read in full and
the creek was traced from the LiDAR instead of OSM. The 4qf map is a freehand schematic (its creek runs EAST from the
Hemlock Hole where the real one runs west), so it fixes the ORDER of things, not their shape: along the Camp Central
loop from the crook clockwise, Dining Pavilion and showers, kitchen, dormitory, Cliffside Stage, Bardic Circle, Coffee
Dragons; the Village Green then the Stone Circle inside the loop; the Big Bottom south of the circle; the Hemlock Hole
at the loop's downstream corner with the Rainbow Bridge just beyond it; the Old Forest and a "Stage" across the
bridge; Hill Top Trail from the Big Bottom up to Hilltop Camp, Main Parking and the Labyrinth; the Great Meadow,
switchbacks and the West Entrance on the PA 26 side; the farmhouse at the main entrance. Laid onto the real tongue
that order puts the Pavilion on the north shelf's big roof, the Stone Circle on the knoll beside it (the guide's
"forested hilltop", which the earlier estimate on the flat Big Bottom was not), the Hemlock Hole at the elbow pool,
the bridge on the west run just west of the pool, and the New Camp Stage at the bridge's south landing. Section 1.3
carries these positions with their uncertainties; `bigdub_site_plan.jpg` and the blockout were redrawn for them.

Under every reading the build is the same terrain, the same creek, the same roads and the same four stage kits; what
moved was which ground gets which name and where the booths sit. **The user can still correct it from memory**
(decision 1); nothing in phase 0 depends on the answer (terrain, frame, walking, stress test); phase 1's camp
placement and phase 2's booth point do.

**Smaller open points** (Appendix D or the user):
1. The Pavilion building itself: which structure, its size, and whether the imagery predates it.
2. Which way each stage faces.
3. Where exactly the Rainbow Bridge crosses: the drone frames show a long cable-stayed timber footbridge over a calm
   reach 25-30 m wide, with forest camps on one bank and an open vehicle field on the other.
4. New Camp's real extent beyond the 2.4 ha west bank strip ("Tent, RV, Car Camping" on both the 2025 and 2026 maps).
5. Which permanent building is Coffee Dragons, and where the Seminar Stage, the Big Bottom and North Crook are
   (names from the guide, section 1.5).

### 1.5 What the 2026 festival guide, the 2025 map and the first photos add (research, read 2026-10-09)
Sources: the official 36-page "BIG DUB Festival 2026" guide (`bigdub_guide_2026.pdf`, text extracted to
`guide_2026_text.txt`), the official 2025 map, the 2026 drone flyover frames and festival photos in the research
folder (Appendix D lists them). Observed unless marked.

- **The Stone Circle** (guide p. 7): begun in 1995 "upon a forested hilltop"; today "over 60 Standing Stones ... outlining
  almost two-thirds of the final 200-foot diameter circle", raised by hand each year at the sanctuary's Stones Rising
  (early September). So: a 61 m diameter arc of 60+ stones, two-thirds closed, the open third facing one way. "The
  beating heart at the center of Four Quarters."
- **The Main Stage is the Stone Circle Stage.** The guide's set times list four stages: STONE CIRCLE (headliners;
  Ravenscoon Thu, Infekt and Eptic Fri, Opiou and Mersiv Sat; it opens around 2-3 PM and closes 11 PM to 12:15 AM),
  HiSCORE (the Pavilion stage's schedule name; runs to 4 AM), HEMLOCK HOLE (to about 4:30 AM) and NEW CAMP (to about
  4 AM). "Opens after Mainstage closes" is said of the Disco Den camp, and the shuttle "operates until after the Stone
  Circle closes each night". Consequence for the look: the Main Stage headliner plays 9-11 PM (full dark in late July),
  the after-hours are the Pavilion, Hemlock Hole and New Camp.
- **Camp Central = the Coffee Dragons Cafe** ("Camp Central for BIG DUB": drinks, ice, ATM, information booth, firewood,
  the emergency line to the Farmhouse Office), with "the upper shower house near Coffee Dragons" and a second shower
  house "in North Crook". EMS: "in Main Camp on the Seminar Stage across from Coffee Dragons and Camp Central", plus
  "the Big Bottom" and New Camp; security hubs "in the heart of Main Camp, and in the White Pines". Shuttle stops:
  Hilltop, Camp Central, North Crook, White Pines. "Fire spinning is allowed on the Mountain"; a Drum Circle is open
  nightly; quiet time 5-11 AM.
- **HiScore** = the HiScore Game Lounge "located at the Pavilion Stage" (2025 map): a retro video-game lounge inside the
  timber-frame pavilion (photos: heavy posts and knee braces, exposed roof trusses, benches, big screens, consoles,
  Nintendo-character cutouts, hanging flowers and string lights), hosting cartoons, Beerio Kart, Emo Night, TRL parties.
- **The Pavilion** is a timber-frame hall with exposed trusses and a wooden ceiling, open on at least one side, used all
  night; its footprint is still unmeasured.
- **The Rainbow Bridge**: a long, narrow cable-stayed footbridge with a planked timber deck and wire rails, crossing a
  calm reach about 25-30 m wide, swimmers on floats beneath it (drone frames t162/t168). Length about 40 m (estimate).
- **Hemlock Hole**: a wide, slow pool with a stony gravel beach on one bank, packed with swimmers and inflatables on a
  hot afternoon (frame t141). The creek's channel there is 40-60 m wide at low water, far wider than OSM's centreline
  suggests (consequence in 5.2).
- **The Main Stage's look** (the festival's own landing-page hero photo, presumably the Stone Circle Stage): a stage set
  among tall straight tree trunks, a wide LED wall flanked by tall LED pillars carrying the festival's spiral motif in
  pink and orange, a truss roof with moving heads, dense green laser fans over the crowd, purple wash and haze. Trees
  stand INSIDE the crowd area. This is the strongest single cue for 6.1 and contradicts an open-field stage.
- **Theme camps**: 16 in 2026 (the map's list) vs 12 in 2025; several are "on the mountain". Frick Frack Blackjack is a
  red-and-white striped big-top tent with string lights and a green felt table (photos); the Illuminarium is UV
  stretch-fabric decor between trees; there is an LED pixel wall in the woods; a parachute game; yoga in the woods.
- **2025 vs 2026 maps**: identical layout and the same four stages (so "New Camp Stage" is not new in 2026); the
  2025 map labels New Camp "Tent, RV, Car Camping".

---

## 2. What "as exact as possible" means here

Three fidelity tiers, so effort goes where exactness is achievable:

| tier | what | how exact | source |
|---|---|---|---|
| A: from data | the terrain, the creek, the field shapes, the tree lines, the roads, distances and slopes, the night sky for the date and place | to the metre | geo |
| B: from photographs | the three stage structures (LED walls, trusses, roofs, decor), the Pavilion building, the standing stones, the Rainbow Bridge, vendor rows, the entrance gates, signage, the 16 theme camps' names | shape and proportion right, sizes to about 10 percent | research (Appendix D) + the map |
| C: plausible | tents, cars and RVs, the crowd, campfires, string lights, the exact placement of 400 small things | the right density in the right place | map + Dino kit |

Rule: tier A is never faked (no "artistic" hills); tier B is modelled from the photo index with its size written next to
each dimension (measured from a photo against a known object, or estimated); tier C follows the map's icons and the
budget. Logos and names (BIG DUB, the theme camps, the stage names) are used as they are: this is a personal recreation
for the user's own stream, not the Tribe pitch, so the pitch's "everything original" rule (club plan risk 11) does not
apply here. Photographs themselves are reference only; nothing downloaded ships in the pak.

---

## 3. Concept and art direction

**One line.** One in the morning at Big Dub: you are the headliner on the plateau, the field below is a bowl of glow,
and if you walk down the gravel road you reach the Pavilion's late set, the creek, the Rainbow Bridge and New Camp's
stage under the trees, with campfires and string lights the whole way.

**Why the real terrain carries it.** The stages sit on a hillside, so from the Main Stage the crowd falls away down the
slope and the lights of Main Camp, Hilltop and the gorge trees are the backdrop; from the bottomland you look UP at the
stage glow on the ridge. Flat festival grounds (Dino, Halloween) never had that. The walk is the content: 70 m of relief,
a gorge, a bridge, three kinds of woods, five camps.

**Palette** (the festival's own: the logo is red-and-gold mushrooms on green):
- Big Dub red (1.0, 0.12, 0.08) and gold (1.0, 0.75, 0.15): signage, the main gate, the LED banners.
- Camp amber (1.0, 0.55, 0.15): tents, lanterns, campfires, string lights. Carries the walk.
- Stage lasers green (0.15, 1.0, 0.25) and the user's VJ colours on the walls. Carries the stages.
- Night blue (0.35, 0.55, 1.0): moonlight, the creek, the sky. Everything else is near black.
- Rule: warm on the ground, cold in the air. Purple and cyan are used only in the VJ content, so the site never looks
  like Dino or Halloween.

**Darkness and comfort.** The Dino night rule (everything dark except the DJ, the visuals, the lasers and the lights) and
the user's comfort rules (no strobes, at most 3 flashes per second, no one-frame hits, no full-frame white, on-beat at
most ~1.6x mid-beat, cue steps ramp over 60 ms) apply unchanged; the Halloween `hw_cuecheck.py` method gates every
animated build.

**Sky.** A real star field for 39.75 N, 78.37 W on the festival's Friday night, rendered into the sky texture by a small
script (a star table, no library needed: the 300 brightest stars + a Milky Way band). Computed on 2026-10-09 with a
mean-synodic moon and a sidereal-time formula (derived; the phase-0 script does the exact ephemeris): at 22:30 EDT
(the Main Stage headliner hour) the Milky Way's core stands due south at 21 degrees altitude with Deneb at 54 degrees;
at 01:00 EDT (the after-hours stages) the core is low in the south-south-west at 15 degrees, the Summer Triangle is
overhead, and the core sets around 03:00. The moon that night is a waxing gibbous, 10 days old, 80 percent lit, up until
after midnight (its setting time is assumed, not computed). Ridge silhouettes come from the DEM (section 5.8), so the
horizon is the real one.

**Audio.** Off, as in the other plans (level audio is untested in Tribe's mix and the stream).

**Mood by set section** (the show in section 8 follows it):

| set section | the Main Stage | the site |
|---|---|---|
| intro | wall dim, a few heads slow | campfires, string lights, the Pavilion's glow across the field |
| build | heads up, the first laser fan | the other stages' walls brighten |
| blackout bar | only the wall | the camps |
| drop | everything, fans over the whole slope | sky beams from the delay towers, the bridge pulses |
| breakdown | wall only | the gorge, the moon on the creek |
| outro | fans alternate | fade to the camps |

---

## 4. Layout: the world frame, the stage variants, and Tribe's fixed constraints

### 4.1 One level, three load transforms
Tribe's DJ rig, the spectator cameras and the mini menu are at the world origin (measured, Session 3t), so the DJ's
stage must be at the origin. With three DJ-able stages 240-400 m apart, the Dino way (one stage at the origin) is not
enough. Two routes:

- **Recommended: one cooked level, loaded at a per-stage transform.** The mod loads custom levels with
  `LevelStreamingDynamic.LoadLevelInstanceBySoftObjectPtr` and already locates the call's `Location` parameter
  (**read**: `em_load_level_soft`, hook/dumper.cpp ~2405; it zeroes the parameter block, so Location and Rotation are
  (0,0,0) today). Writing a Location and a Rotation there loads the same level instance translated and turned, so that
  the chosen stage's booth lands at the origin. The same pak serves three menu boxes (or one box plus a setting); the
  level content is built once, in the site frame. The change is about 20 lines in the hook (section 7.5) plus one
  prop_offset lookup for `Rotation` (assumed to exist by that name: it does in the UE 5.4 signature; the first log line
  confirms it).
- **Fallback: three cooked maps** (`Environment_BigDub_Main`, `_Pavilion`, `_NewCamp`) in the same chunk, sharing every
  mesh and texture (the pak grows by three small .umap files only). No hook change for the load, but three boxes in a
  four-box menu (section 10.4) and the collide file still needs a variant name.

Consequences of the transform route, all handled in the generator:
- Everything is unlit or VAT/WPO in object space (Dino's materials), so a level-wide transform costs nothing.
- The sky dome must be big enough that a 600 m offset does not show: radius 4,000 m (Dino's is 480 m).
- Each stage carries its own pair of deck lamps (DeckLamp names per stage); `lights.txt` scales them by name.
- The visuals screen lookup is by mesh asset name (**read**: `em_find_mesh_actor("SM_DinoVisualScreen")`, dumper.cpp
  ~2284), so the three walls get three asset names and the mod is told which one is the backdrop for the active variant
  (section 7.5). The other two walls run the cue-driven VJ material (section 8.3).

### 4.2 The site frame and the three transforms
Site frame = the crop frame of section 1 turned into Unreal's hand: X east, Y north (= minus crop y), Z = elevation
minus 230 m, metres in Blender, centimetres in Unreal. The generator models the whole site in it. For each variant the
stage's booth point B and facing yaw f (the direction the DJ looks, over the crowd) define the transform T that maps
B to the origin and f to minus Y (the Dino frame: the DJ faces -Y, the crowd is toward -Y, the stage behind at +Y).

| variant | booth point (crop x, y) | deck top elev | facing (compass) | basis |
|---|---|---|---|---|
| Main (Stone Circle Stage) | 1210, 130 (+/-40 m) | 253.5 (252 + 1.5 deck) | west, along the knoll's flat top, the stones flanking the stage, the crowd on the top and spilling down the gentle west side toward Camp Central | the circle's position (1.3); "Big Dub's largest stage sits inside the circle" and stones "at both sides of the stage" (research, D.4); the Big Dub map draws the Stone Circle Stage next to the Pavilion in Camp Central; facing **assumed** (west is the least steep direction; south is a 15 percent drop) |
| Pavilion | 1072, 76 | 247.6 (the hall's floor + 0.6) | south-east, out of the hall's open side into Camp Central | the big roof (1.3); facing **assumed** |
| New Camp | 1060, 650 | 244.5 | south-west, down the neck into the Old Forest | the 4qf map's "Stage" just south of the bridge; the Big Dub map's New Camp Stage at the bridge's far end; **assumed** +/-50 m |
| (Hemlock Hole, no DJ variant) | 1140, 570 | 230.5 | north-east, the crowd up the gentle slope into White Pines | "on the bank above the pool with the bridge beside it" (research), the beach side of the elbow pool; facing **assumed** |

The stage decks are 1.5 m above the ground at the booth; Tribe's floor (z=0) is each deck's top after its transform, so
the DJ stands on the real deck and the crowd field is 1.5 m below, like Dino's riser. Stairs at the side of each deck are
floors in the walking map (the club's stairs method).

### 4.3 Fixed by Tribe (measured, Sessions 3t and 3v; world cm, per variant after the transform)

| thing | value | consequence |
|---|---|---|
| DJ rig BP_Rig_C | (-5, 31, 78), PlayerStartDJ (-6, 87, 1) facing -Y | the booth table top at 74 cm, x -95..85, y -5..50 (Dino TABLE) on every stage's deck |
| Table height handle | user-adjustable | a static booth front fits one height (the Dino caveat) |
| SpectatorBoundingBox | x -250..250, y -221..279, z -6..494 | no set geometry inside it on any stage: the LED wall starts at y >= 2.8 m; the deck itself is fine |
| SpectatorCamera1 | (-2, -86, 176) looking +Y | the stream shot: the DJ with the wall behind; each stage is composed for it |
| BP_MiniMenu | (-5, -6, 93), box x -73..65, z 89..191 | nothing inside |
| Pointer / menu rays | line traces | every StaticMeshActor NoCollision (Session 3q); walking collision is the mod's (section 7) |
| Visuals wall UVs | Tribe's back-wall layout | `visual_screen_uv` copied on all three walls |

### 4.4 Top-down sketch (crop metres, north up; not to scale)

```
 y=-50   ~~~~~~ creek north run, flowing WEST from the Silver Mills bridge to the NORTH CROOK hairpin (930, 0) ~~~~~~
 y=50-130   CAMP CENTRAL shelf 244-250 m: [PAVILION + HiScore (1072,76)] kitchen, dorm, showers, Coffee Dragons
 y=50-100                                      VILLAGE GREEN + in-camp parking (1150-1280)    hill 258 m (1290,120)
 y=130          (o) STONE CIRCLE 61 x 49 m on the knoll 252 m, [MAIN STAGE (1210,130)] at its east end, faces W
 y=140-260   the knoll's slopes: hardwoods, 250 -> 230 m (the crowd spills down here)
 y=200-520  the BIG BOTTOM 229-236 m, flat: Members Camp, Main Camp tents, theme camps   HIGH MEADOW 245-259 m
   |  middle arm of the creek runs SE down the tongue's south-west side                   (1300-1500, 330-520)
 y=520-590      WHITE PINES: EMS, ice, shuttle, Fox Altar      [HEMLOCK HOLE STAGE (1140,570), faces NE]
 y=420-600   HEMLOCK HOLE = the elbow pool (1170-1240), 227 m, beach on the tongue side, cliff on the SE bank
 y=585-640   ==RAINBOW BRIDGE== (1110) over the west run, ~60 m, deck ~236 m, north bank -> the neck's terrace
 y=560-620   <--- the west run flows WEST from the elbow; Beaver Dam foot crossing further down (~950,560)
 y=620-720   the NECK 236-262 m: [NEW CAMP STAGE (1060,650), faces SW]    stalls row on the bluff (1066,659)
 y=400-840   THE OLD FOREST = the peninsula (330-1000): New Camp tents, altars, Lower Switchback from PA 26
 y=700-1230                                   HILLTOP pasture 230-276 m: Main Parking, Hilltop Camp, RV camping,
 y=800                                        LABYRINTH (1147,800) 275 m; RV LAND / Farm Fields below, Loft & Shop
 y=700-760   creek ESE run along the peninsula's south side, then SE to the gorge at (960,900)
 y=900-1340  GORGE (x 930-970, 221 m) | west: GREAT MEADOW / NEW CAMP strip + field + switchbacks to the PA 26 gate (743,1251)
 y=1281  FARMHOUSE / CAMP OFFICE / MAIN REGISTRATION (1084,1281) ---- Walker Lane 564 m east ---- MAIN ENTRANCE (1668,1286)
 y=1340  Big Pool + river foot crossing (930,1340)      y=1450 creek south run      PA 26 beyond, Fairview Station W
```

Walking distances (geo, straight line): Main Stage to the Pavilion 150 m; Main to the Hemlock Hole Stage 445 m; Main
to the bridge 470 m; bridge to the New Camp Stage 70 m; Main to the Labyrinth 675 m; Main to the farmhouse 1.16 km;
Main to the main entrance 1.6 km. The real festival's own figure: "New Camp to Coffee Dragons is no further than a walk
to Main Parking" once the bridge opened. A full lap Main Stage, bridge, New Camp, Hilltop, Main Stage is about 2 km,
18 minutes at walking speed, which is why section 7 adds a run speed and the shuttle stops.

---

## 5. The site, piece by piece (tier A and tier C)

All of it is generated in `bd_site.py` and its modules (section 10.1), baked with Cycles where the Dino pipeline bakes,
exported as FBX per surface, imported by `build_bigdub.py`. Tris and sizes are estimates unless marked.

### 5.1 Terrain (SM_BdTerrain_<tile>, SM_BdTerrainMid, SM_BdTerrainFar)
- Source: `dem_crop.npy` (geo). Three resolutions in nested rings:
  - core, the walkable site x 350-1800, y 60-1550 (1,450 x 1,490 m, reading D: the tongue, the Old Forest, the
    Hilltop pasture, New Camp and the farmhouse): a 3 m grid cut into a 4 x 4 set of tiles (~360 x 370 m each), about
    240k quads = 480k tris for the whole core, about 30k tris per tile. Each tile is its own actor so frustum culling
    drops the ones behind you; with the site this long, at most 5-6 tiles are ever in view.
  - mid ring to the crop edge (2 x 1.8 km): 12 m grid, ~18k tris, one actor.
  - far ring: the rest of the 10 km DEM tile at 64 m, ~24k tris, one actor, black with the sky behind it: the real
    ridge lines (Town Hill to the north-east, the hills across PA 26).
- Creek channel and the gorge banks come straight from the DEM (the 1 m data resolves the channel; the 3 m core grid
  keeps the bank shape).
- Material (fork-cooked, phase 0 proves it): one terrain material with four tiling detail layers (grass, mown grass,
  dirt road, gravel; 1024 px, ~0.5 MB each in ASTC) blended by a 2048 splat map painted from `masks.npz` plus the
  roads, multiplied by a baked light/AO map (4096 over the core: moonlight, the camps' light pools, the stages' washes;
  2048 over the mid ring). Tiling detail at 1 m per repeat gives crisp ground at the DJ's feet and under a walker;
  a single baked albedo at 4096 over 1 km would be 25 cm per pixel, which is blurry at 2 m. The Dino ground bake stays
  as the fallback if the material misbehaves (measured: the Dino 320 m ground at 4096 reads fine from the deck).
- Night: the baked light map carries the darkness (NIGHT 0.5 exposure rule); the splat albedos are dark to start with.
- Tris: ~270k total, ~90k in view (core tiles in the frustum + mid + far).

### 5.2 The creek (SM_BdCreek)
- A ribbon mesh along the LiDAR-traced channel (`creek_path.json`: 2,300 points in downstream order with the water
  surface elevation; OSM's line is not used), 9 m wide at riffles and widening to the DEM's flat-water extent at the
  pools (the elbow pool is 25-30 m wide for 200 m), from the north run round the tongue, the peninsula and the gorge
  to the PA 484 bridge: ~3.2 km inside the crop, ~3k tris.
- Material (fork): a dark blue-black water with a scrolling normal/shimmer (two noise tiles, like the fog sheets) and a
  moon glint band; emissive floor so it never goes fully black. Stock fallback: a dark blue translucent MIC.
- The swimming holes (4qf names six): the Hemlock Hole at the elbow (5.6 and 6.4), the North Crook hole at the hairpin,
  the Stone Ledge hole on the middle arm, Big Pool at the gorge's south bend; each a wider pool with a gravel or shale
  beach on the inside of its bend, a shale ledge or cliff on the outside, a few people on the rocks (tier C).
- Walking: water is a no-walk region in the collide file (section 7.3), except the bridge and the beach steps.

### 5.3 Roads and paths
- Gravel: the Loop Road (the N-S farm road up the plateau's west side, **geo**), Bridgeport Road (SE corner up to Ridge
  Road, geo), the south farm road (geo), the west bank track (geo), White Pines Loop and New Camp Loop (map, placed on
  the mowing lines the aerial shows). Painted into the splat as gravel 4 m wide; dirt paths 2 m between the camps.
- Festoon lights on 5 m poles every 25 m along the main paths (the Dino `string_lights` helper), warm amber, a light
  pool per pole in the ground bake.
- Signposts at the junctions (the real ones use painted boards: "MAIN CAMP", "NEW CAMP", "SHUTTLE") in the kit's font.

### 5.4 Trees (SM_BdTreesNear_<region>, SM_BdTreeCards_<region>, SM_BdTreesFar)
- From `masks.npz`: 207 ha of deciduous woods and 54 ha of evergreen in the crop; about 55 ha of that is inside the
  walkable core. At one tree per 40 m2 that is ~14k trees in the core and ~50k beyond it.
- Three kinds:
  - near trees (~1,800): within 40 m of any walkable field edge, road or stage. Hemlock and white pine as layered cones
    with a trunk (~220 tris), oaks and maples as a trunk plus 3-4 crown lobes (~300 tris), 12-28 m tall. Vertex colour
    for the bake; show-lit near the stages.
  - card trees (~12k): two crossed masked quads with a baked tree atlas (2048, four species x two sizes), 4 tris each,
    merged per region (9 regions following the core tiles). Masked, not translucent: no overdraw cost beyond the alpha
    test, which the Quest handles for cards at this count (assumed; the phase-0 stress level measures it).
  - far trees (~20k): the Dino trick, black glow silhouettes 8 tris each, one mesh, only on ridge lines that the sky
    shows them against; the rest of the far woods is the dark terrain colour.
- Budget: near 1,800 x 260 = 470k tris total, of which ~120k in view with region culling; cards 48k; far 160k but one
  cheap unlit draw. MaxDrawDistance 220 m on the near-tree actors and 900 m on the cards.
- Cut if late: half the near trees (keep the ones along the walk lanes).

### 5.5 Camps (SM_BdCamps_<region>, SM_BdCampGlow)
- A tent kit in `bd_kit.py`: dome tents (3 sizes), canopies (3 x 3 m EZ-ups, the festival staple), cars, pickups, RVs and
  trailers, camp chairs, coolers, a lantern per third tent (glow), flags and totems on poles, hammocks between trees in
  the Old Forest, shade cloth, string lights between canopies. All boxes and tubes with baked vertex colour; 12-80 tris
  each.
- Density per area (tier C, from the map's area sizes and a 2,500-person festival, **estimate**):

| area | extent (crop m) | tents | vehicles | notes |
|---|---|---|---|---|
| Camp Central | 985-1130, 80-240 | 40 | 15 | the service cluster: Coffee Dragons' deck, the kitchen, the dormitory, the Upper Shower House, vendors, EMS, merch, info; in-camp parking rows along the creek at North Crook |
| the Big Bottom and Members Camp | 1030-1250, 260-560 | 130 | 0 | flat bottomland: Members Camp's wooden tent platforms, theme camps 04-06, the crowd field in front of the Main Stage stays clear |
| Main Camp tent camping | 1150-1300, 440-600 | 100 | 0 | forested slopes inside Loop Road; theme camps 07-10 as compounds with canopies and signs |
| High Meadow | 1300-1500, 350-520 | 70 | 10 | scrub meadow with small conifers; RV camping on Ridge Road beside it |
| White Pines | 1050-1150, 540-620 | 40 | 0 | under the pines at the elbow; EMS and ice tents, the shuttle stop |
| the Old Forest | 450-980, 400-880 | 120 | 0 | hammocks and tents between trunks, the Old Forest Stage's clearing, theme camps 11-16 near the New Camp Stage |
| New Camp (strip and field) | 885-952, 1010-1320 and 700-770, 1000-1070 | 90 | 50 | creek-side tent camping on the strip, car camping and glamping bell tents on the field and slope, New Camp check-in and EMS at the PA 26 gate |
| Hilltop pasture: Main Parking, Hilltop Camp, RV Land | 1000-1300, 700-1230 | 120 | 260 | rows of cars at the north end (Main Parking), RVs along Ridge Road and in RV Land (the central field), theme camps 01-03, the Labyrinth with its four solstice poles, the school-bus shuttle at the stop |
| the farmhouse cluster | 1000-1300, 1230-1310 | 10 | 30 | staff vehicles, the Loft & Shop, the winery, orchards |

- About 720 tents, 365 vehicles, 180 canopies. Tris ~160k total, ~50k in view. Lantern glow and string lights are
  the "always" cue row with a 2-4 Hz flicker at 15 percent (the Halloween grounds flicker), never a flash.
- Campers: 300 static people (crowd3 bodies in the "far" tier, sitting and standing poses) at the camps and on the
  paths, plus the walking map's soft "person" circles for the ones near lanes.
- Cut if late: vehicles become plain boxes; Hilltop and High Meadow drop to half density.

### 5.6 Camp Central, vendors, infrastructure and the small landmarks (SM_BdProps_<region>)
From the map's icons, each with a position on the site plan (map unless marked):
- Camp Central (the tongue's north shelf, 1.3), in the 4qf map's order from the crook eastward: the Pavilion with the
  Starvin' Artist kitchen attached (section 6.2, the big roof at (1072, 76)), the Upper Shower House (the second roof),
  the In-Camp Dormitory (plank walls, a porch), the Cliffside Stage (a small permanent stage: the 24 x 24 ft stage with
  10 ft to the rafters), the Bardic Circle (a ring of log benches), then Coffee Dragon Hospitality at the shelf's east
  end: the Coffee Dragons' Lair (a shaded deck cafe: ice, firewood, the information booth, first aid, camp services,
  showers and flush toilets); the Village Green (a mown lawn) and the in-camp parking loop east of the dormitory; the
  Fire Circle inside the loop = Four Quarters' Upper Fire and Drum Circle, an 85 ft (26 m) sanded ring inside a 75 ft
  timber arbor with a 46 ft open centre, where Big Dub runs flame jets (the Halloween fire cards on the "fire" row).
  Big Dub adds (2025 vendor list, D.5): Wok N Tok, Naders Bistro, Sassy Wraps, Puttin' on the Mitts as food units
  (the Dino vendor kit with those names), BIG DUB MERCH, EMS tent, the Sanctuary (a lotus-icon chill tent), Harm
  Reduction, the shuttle stop, ADA parking. Down the hill at North Crook: the Lower Shower House, the River Side Fire
  Circle, in-camp parking rows along the creek, the North Crook swimming hole.
- Main Camp: two vendor rows (V) along the field's long sides, food vendors, the Help Station, Harm Reduction, Ice, the
  Frick Frack Blackjack tent (a card-table canopy with a neon sign), the Fox Altar (a small shrine with candles and
  offerings under a tree, map icon), shuttle stops at White Pines and North Crook (the map's shuttle info lists Hilltop,
  Camp Central, North Crook, White Pines).
- The Rainbow Bridge (research, D.3, the deck photo and the 2026 flyover): a 2018-19 pedestrian suspension footbridge:
  steel A-frame pylons at each end on wooden landing decks with rails, two main cables, vertical hangers, a plank deck
  about 1.5 m wide, chain-link mesh side panels about 1.1 m high, the deck sagging toward mid-span, 8-10 m above the
  water; the night photo shows strip lights along the pylons and hangers. Site (1.3): across the west run at x about
  1110, just west of the elbow pool, from the tongue's south tip (north bank, 228 m) to the neck's terrace (south bank,
  240 m): about 60 m between the banks' tops, the deck at about 236 m mid-span. Model it that way, with the strips in
  six rainbow bands (the map's rainbow) pulsing on the "always" row, and swimmers on floats in the pool below. The
  bridge deck is a walking floor (8 segments following the sag); the pylons and mesh are boxes. The Beaver Dam foot
  crossing (4qf) 150 m further downstream is a line of stepping stones, walkable at a crouch (a floor strip 0.6 m
  wide).
- New Camp: the New Camp check-in and EMS at the PA 26 entrance, the Wolf Altar, glamping bell tents, food vendors, ADA,
  ice, theme camps 11-16 (Flow With Us, Scratch Camp, Camp Truffle, The Sauce Sanctuary, Disco Den, CareSquad HQ).
- Hilltop (the pasture): RV camping, theme camps 01-03 (Camp Portal, Graveyard Smash, Flow Therapy for Mind & Body),
  ADA, ice, the shuttle stop with the school-bus shuttle, the Labyrinth (76-84 ft of concentric mown rings with granite
  curbs, four tall wooden solstice poles on the rim, solar lights, and Kikiwawa the yellow mascot inflatable at its
  centre as the 2026 drone frames show), Main Parking's car rows at the north end, the camp offices at the farmhouse
  (MAIN REGISTRATION signs), the main entrance gate on Walker Lane (a BIG DUB arch, the swirling logo with mushrooms as
  a baked texture painted by us, not downloaded), Mushroomland (giant inflatable red-capped mushrooms and pink/purple
  flowers) near Camp Central.
- The tongue's west side along River Road: the River Side Sweat Lodges (low tarp domes about 2.5 m across with a Welcome
  Fire and a stone-heating pit, by the creek), the Fairy Cairn (a knee-high stone cairn hung with baubles and lights
  on the riverbank), the Stone Ledge swimming hole, theme camps 04-06 (Lucid District, Illuminarium, The Expanse);
  Members Camp's wooden tent platforms on the forested slope above the Big Bottom.
- A shuttle bus (one, parked at the Camp Central stop; a second on Ridge Road), the real route's stops signed.
- Tris: ~90k total.

### 5.7 The Stone Circle (SM_BdStoneCircle)
From the guide and the research (1.5, Appendix D.3): an ellipse 200 ft east-west by 160 ft north-south (61 x 49 m), laid
out on true north in 1995 and turned 12 degrees west of north to fit the land; over 60 standing stones outlining
almost two-thirds of it; sandstone slabs from western Maryland quarries, typically 10,000-14,000 lb, up to 14 ft (4.3 m)
tall, 8 ft wide and more than a foot thick, on concrete footers; the Flame Stone (22 ft, 4 t, red-brown-grey) stands in
the north as the first stone of an inner ring; the Mother Stone (13 ft, reddish) has an 18-inch drilled portal; the West
Gate is a pair with a 20 ft gap; the North Copse is a 45 x 30 ft inner ellipse of ~12 ft beige slabs set almost
touching (built 2019-2025). The floor is bare packed dirt under tall straight hardwoods, with log benches, a draped flat
North Altar slab, and a dirt path along the stones; no central fire pit is documented. Big Dub's largest stage stands
inside the circle, with hammocks in the trees at the crowd's edge.
Model: 62 slabs on the 61 x 49 m ellipse over a 240 degree arc, 2.0-4.3 m tall, tan-brown sandstone with a baked texture
(the Flame Stone 6.7 m, the Mother Stone with its portal, the West Gate gap), the North Copse inside, the dirt floor as
a splat layer, log benches, the altar; the open third faces west, where the crowd flows in from Camp Central. Position:
the knoll beside Camp Central, centre (1180, 130) +/-40 m, top 252-253 m (1.3); the circle's floor follows the knoll's
3-5 m of relief (real circles are not flat); the trees inside the crowd (6.1) are the circle's own hardwoods. People
stand among the stones; walking treats each stone as a box. The 25 m ring on the Hilltop pasture is modelled separately
as the Labyrinth (5.6).

### 5.8 Sky and horizon (SM_BdSky, SM_BdTerrainFar)
- Sky dome r = 4,000 m, texture T_BdSky 4096 x 2048: the star field of section 3 (procedural from a star table), the
  Milky Way band, a faint horizon haze, no moon in the texture (a moon disc mesh if the phase for the date has one up at
  1 AM: computed in phase 0). Luma caps as Halloween's sky (never above 35 percent).
- The far terrain ring is the real horizon; the sky texture needs no painted hills.

---

## 6. The stages (tier B: the research photos decide the final shapes)

Every stage follows the Dino set contract: a baked set mesh, a rig mesh with lens glows, beams and halos as translucent
quads on cue rows, lasers with the UV1-4 sweep contract, a VAT crowd, a visuals wall with Tribe's UVs, deck lamps. The
**physical descriptions below are the plan's defaults from the map and the site**, written to be replaced line by line by
the research findings (Appendix D) in phase 2; each size is marked estimate until a photo measure replaces it.

### 6.1 The Main Stage (Stone Circle Stage) - the DJ variant "Big Dub"
- **Site**: inside the Stone Circle on the knoll beside Camp Central, booth (1210, 130) +/-40 m at the ellipse's east
  end, deck top 253.5 m, facing west along the knoll's flat top (assumed: it is the least steep direction and it points
  the crowd at Camp Central, 150 m away, where the Big Dub map draws the two stages side by side). The crowd: the
  knoll's 60 x 40 m flat top inside and around the stones, the gentle 244-250 m shelf west of it toward the Pavilion,
  and spilling down the hardwood slope to the south-west (250 to 230 m over 150 m); a fan 90 m deep and 60 m
  half-width, about 2,000 people, standing stones around the stage and in the front third of the crowd, tall trunks
  through the whole field, hammocks at the edge. From the decks the view is the stones, the trunks, the Pavilion's glow
  at the far end, the Big Bottom's campfires below to the left and the dark ridge of Town Hill beyond. If the position
  or facing moves (the +/-40 m, or the user's memory), only the booth point and yaw in 4.2 change.
- **Structure (the 2026 design, from the photos and frames, Appendix D.4 and D.5; sizes estimated)**: a stage among
  tall straight trunks, not in an open field: the nearest trees stand inside the crowd and in front of the wall. A low
  deck 20 x 10 m, 1.5 m high, with the DJ booth's front itself an LED panel; a flat box-truss roof about 10 m high
  carrying about eight moving heads plus LED batten/strobe bars and blinders on the front truss; a centre LED wall
  about three panels wide (about 14 x 6 m, Tribe's backdrop in this variant); two tall portrait LED pillars (about
  1.2 x 9 m) on scaffold towers each side near the stage plus at least three more per side out among the crowd, all
  playing the festival's spiral content (the VJ-wall material); the glowing sun/flower emblem with rays above the wall
  (the 2023 silver sun, lit); black PA stacks either side (flown line arrays plus ground subs in 2023); purple wash and
  heavy haze; laser fans from both sides crossing over the crowd in cyan/white, red+purple and green; blue inflatable
  jellyfish and white spiky flower sculptures hung in the trees (masked cards with glow on the "always" row), red/pink
  stretch-fabric shade sails overhead; delay towers out on the slope; a FOH tent at about 45 m; 10 x 10 canopies at
  the crowd's edges; barrier 4 m from the lip. Option (decision 9): the 2023 painted knotwork serpent facade flanking
  the stage, as a baked texture painted by us. So the site keeps 25-35 near trees inside the crowd field (the circle's
  own hardwoods), which gives the lasers something to cut through and the walkers something to weave between.
- **Rig**: 24 moving heads (8 on the roof's front truss, 4 per PA tower, 8 on the deck as uplights), 4 sky-tracker
  units on the delay towers, 2 follow spots at FOH. Lasers: 5 fans from the roof's front truss (green and the VJ colour)
  sweeping over the bowl; clearance gates as Halloween (no beam within 0.46 m of the set, DJ head gap >= 4.9 m,
  nothing across the wall, lanes checked at 27 poses).
- **Crowd**: 2,200 (crowd v3, 140 BPM, rave attire, totems, glow), tiered by distance from the DJ (near < 9 m ~150
  people at 874 tris, mid to 25 m and along the walk lanes at 256, far at 21), plus the section 7.4 walk-lane rule.
- **Stream shot**: SpectatorCamera1 sees the DJ, the wall and the roof truss; the bowl and the circle are in the drone
  reel (Appendix A).

### 6.2 The Pavilion Stage (+ Hiscore) - the DJ variant "Big Dub: Pavilion"
- **Site**: the big dark-roofed building on Camp Central's north shelf, (1072, 76) +/-30 m, floor about 247 m, "perched
  on the hillside above the creek": the north run is 40 m north and 17 m below it; 150 m west of the Main Stage (the
  real festival schedules them so sets do not clash; here both walls glow, only the DJ's stage plays the user's
  visuals). The kitchen is attached, the shower house and the dormitory are its neighbours, the Village Green and the
  in-camp parking open east of them, North Crook is down the hill to the west.
- **Structure**: Four Quarters' "New Dance and Dining Pavilion" (2010): a 70 x 30 ft (21.3 x 9.1 m) timber post-and-beam
  hall with arched knee braces, open sides with a perimeter rail, a wooden deck floor on concrete piers, a green
  standing-seam metal gable roof, a sprung dance floor, exposed trusses and a boarded ceiling, long tables by day
  (research: 4qf camp tour + photos; roof pitch, post spacing and floor height are not documented: default 6 bays of
  3.5 m, eaves 3.6 m, ridge 6.5 m, floor 0.6 m above grade). The stage is at one gable end: an 8 x 4.5 m LED wall, the
  deck floor as the stage (the DJ stands on z=0 via the transform), trusses hung from the roof beams, haze. **HiScore** is inside the same hall: the retro game lounge, benches facing
  big screens on the side walls, consoles, Nintendo-character cutouts, hanging flowers, string lights and small moving
  heads on the beams (photos). At night the hall glows from inside; its posts and trusses are the silhouette.
- **Rig**: 12 heads on the roof beams, 2 laser bars at the back wall, LED strips along the eaves and posts (chase), 4
  string-light runs; no sky beams (indoor rule: beams end on the roof and the posts, the club's `laser_spot` method).
- **Crowd**: 500 under and around the roof, dancing close (mid tier within 10 m of the booth).

### 6.3 The New Camp Stage - the DJ variant "Big Dub: New Camp"
- **Site**: the terrace at the Rainbow Bridge's south landing on the neck, default (1060, 650) +/-50 m, 243 m, facing
  south-west down the neck into the Old Forest (the 4qf map draws a "Stage" just south of the bridge; the Big Dub map
  puts the New Camp Stage at the bridge's far end with the Old Forest beyond; the 2019 map called it the Old Forest
  Stage; facing assumed). The crowd stands on the neck's slope and the Old Forest's edge, 450 people, conifers on both
  sides, the bridge's rainbow behind the crowd and the Hilltop bluff rising to the east. If the bridge lands further
  west along the run, the stage slides with it.
- **Structure (from the smaller-stage photos, D.4; sizes estimated)**: a low deck 12 x 7 m, 1.0 m high, a truss frame
  carrying a white fabric projection screen about 7 x 4 m as the backdrop (Tribe's video plays on it in this variant,
  as a 16:9 picture on the white cloth; the VJ-wall material otherwise), PA stacks on truss either side, a painted
  banner on the booth front, a small truss roof with 8 heads, lanterns and string lights in the trees, a NEW CAMP
  sign in the kit font.
- **Rig**: 12 heads, 2 laser fans aimed down the strip (the trees are the clearance obstacle: lanes checked against the
  near-tree meshes), tree uplights in amber and green on the "wash" row.
- **Crowd**: 500.

### 6.4 Hemlock Hole Stage (no DJ variant; decision 4)
- **Site**: the beach side of the elbow pool, the tongue's south tip, default (1140, 570), 229 m, facing north-east so
  the crowd stands up the gentle slope into White Pines and the stage has the pool, its shale cliff (the south-east
  bank, 254 m) and the hemlocks behind it; the Rainbow Bridge is 40 m to its west ("on the bank above the pool with
  the bridge beside it", research). 400 people, with swimmers and floats on the pool below by day and a few at night.
- **Structure**: the small ground-support "goal-post" truss stage of the 2024-2025 frames (D.5): two truss towers and a
  top truss with moving heads over a 12 x 7 m deck, a white projection screen on the truss running the VJ-wall
  material, PA on truss, 8 heads, 1 laser fan; the under-the-sea decor (a purple-pink inflatable octopus on top of the
  truss, inflatable jellyfish in pink, yellow, green and cyan in the surrounding trees, a green neon dinosaur on a
  tower, a canopy tent beside it, a barricade) is given to this stage because of the swimming hole, though the frames
  do not name it; the pool below with its gravel beach, a few swimmers and floats, the shale cliff opposite, hemlocks
  over the water.
- Built with the same kit as New Camp, so it costs a day, not a week; it makes the walk from Main Camp to the bridge pass
  a lit stage.

### 6.5 Crowd and tri budget across the four stages

| stage | people | near | mid | far | tris (estimate) |
|---|---|---|---|---|---|
| Main | 2,200 | 150 x 874 | 500 x 256 | 1,550 x 21 | 292k |
| Pavilion | 500 | 0 (not the DJ's view in the Main variant) / 80 in its own variant | 150 x 256 | 350 x 21 | 46k (116k in its variant) |
| New Camp | 500 | 0 / 80 | 120 x 256 | 380 x 21 | 39k (109k) |
| Hemlock Hole | 400 | 0 | 60 x 256 | 340 x 21 | 23k |
| campers | 300 | 0 | 0 | 300 x 60 | 18k |

The near tier moves with the variant: the generator builds each stage's crowd twice (its "DJ" version with a near tier
and its "far" version without), and the level holds the far versions of the other stages per variant... which means the
level differs per variant after all. Resolution: the near tier is a separate mesh per stage (SM_BdCrowdNear_<stage>)
that the mod hides for the two non-DJ stages (one `SetActorHiddenInGame` per variant; the hook already reads bHidden on
actors, **read**: `em_actor_hidden`). Fallback: ship all three near tiers (about +170k tris) and let the fps gate decide.

---

## 7. Walking the site (locomotion)

### 7.1 What exists (read from `hook/club.cpp` and `hook/club_collide.h`, 2026-10-09)
- Walking works on any custom stage that ships `tribemod/<folder>_collide.txt`, `<folder>` being the lowercased name
  under /Game/Mods/ in the level's path (so `/Game/Mods/BigDub/...` reads `bigdub_collide.txt`); no file, no walking.
- The map holds `rules` (step 45 cm, head 190, knee 25, radius 20, core 15), `floor` rects (a walkable top with a
  solid down to `bot`), `box` and `gate` prisms, `circle` posts, `person` soft dancers, named `spot`s. Limits: 128
  floors, 256 boxes, 512 circles, 1,024 persons, 8 spots (`CC_MAX*`). `cc_floor_at` picks the highest floor rect under
  the point within `step` of the current height; every check is a linear scan.
- Left stick walks where you look (1.8 m/s default, `club.txt` speed=), right stick snap-turns 30 degrees, the right stick
  held 1 s returns you to the decks; stairs ease over 0.2 s; the crowd is soft (slows and steers); VROrigin is moved
  relative to its parent, with safety resets if Tribe moves it.
- The Dino session integrated it (`dino_collide.txt`); the club's full-hall walk test is the acceptance method.

### 7.2 What Big Dub needs (changes to the club session's two files, handed over as patches)
1. **A heightfield floor.** New line type `height <x0> <y0> <cell> <nx> <ny> <zscale>` followed by `nx*ny` values
   (or a sidecar binary `bigdub_height.bin` of int16 centimetres, because megabytes of text parse slowly on the Quest:
   the core at 1 m is 1,450 x 1,490 = 2.2 M cells; at 2 m it is 540k cells = 1.1 MB). `cc_floor_at` samples it bilinearly and
   treats it like a floor whose top varies; a slope limit (35 degrees, `rules` gains a field) refuses moves up steeper
   ground, and a `nowalk` mask (the creek, the gorge cliffs, the stage decks' fronts) comes from a second byte grid.
   Floors (decks, stairs, the bridge, the pavilion floor) still win over the heightfield where they overlap.
2. **Limits and speed.** CC_MAXF 128 -> 512 (stairs on four stages, the bridge in segments), CC_MAXB 256 -> 2,048
   (tents, vendors, vehicles, stones), CC_MAXC 512 -> 8,192 (near trees, posts), CC_MAXP 1,024 -> 6,144 (the crowds
   near lanes), CC_MAXS 8 -> 32 (four decks, guest spots, shuttle stops). With those counts the linear scans must go: a
   uniform grid (50 m cells) built at parse time, so each frame touches the shapes in the 3 x 3 cells around you.
   The on-device flood-fill test (`tests/club_collide_test.cpp`) runs over the whole site at 1 m: every lane the map
   shows must be reachable from every deck, and the creek, the gorge and the stage fronts must not.
3. **Run.** Left stick click toggles run (4.5 m/s) so the 1.3 km round trip is 5 minutes instead of 12; `club.txt`
   gains `run=`.
4. **Shuttle stops (decision 6).** Four `spot`s named `shuttle_*`; standing on one and holding the right stick click for
   1 s moves you to the next stop with a 0.5 s fade (the club plan's `StartCameraFade` assumption, checked in its phase
   2). The real festival's shuttle, as fast travel.
5. **Stage hop (phase 4).** Walking onto another stage's deck and holding the click reloads the level with that stage's
   transform: the variant switch without the menu. It is the env menu's own load path with a different transform, so it
   costs the load time (1-2 s) and nothing else.

### 7.3 The collide file for a site (bd_collide.py)
- One source file in the site frame, `bigdub_collide.txt` plus `bigdub_height.bin`, with a `frame` line; the mod
  transforms positions by the active variant's transform at load (7.5), so one file serves all three variants.
- Contents: the heightfield (core only; outside it the mod refuses moves: "the festival ends here" at the real fences
  and the creek), floors for the four decks (top at deck height, with stairs: 10 steps of 15 cm at each deck's side),
  the pavilion's floor, the bridge (8 floor segments following its deck), the swimming-hole beach steps; boxes for every
  tent, canopy, vehicle, vendor unit, building, stone, PA stack; circles for near trees and poles; persons for everyone
  within 15 m of a lane; spots: `decks_main`, `decks_pavilion`, `decks_newcamp`, `shuttle_campcentral`,
  `shuttle_hilltop`, `shuttle_northcrook`, `shuttle_whitepines`, `guest_floor` (the field in front of the active deck).
- The top-down check image (the club's method) is drawn over the site plan, so every wall is checked against the aerial
  before it reaches the headset.

### 7.4 The crowd when you walk through it
Walking into a far-tier crowd (21 tris a person) would look bad at arm's length. Rules:
- anyone within 6 m of a walk lane, a vendor row or a stage's side stairs is mid tier (256 tris);
- lanes through each crowd follow the real festival's gaps (the sound tower alleys, the barrier walkway);
- the soft-crowd steering keeps you in the lanes unless you push; the "core" radius stops you walking through bodies;
- the dense front rows (far tier) are fenced off from the lanes by the barrier walkway, as at a real festival.

### 7.5 Hook changes outside club.cpp (the env menu, Dino session's file; a patch)
- `tribemod/envs.txt` lines gain an optional variant: `Big Dub=/Game/Mods/BigDub/Maps/Environment_BigDub@main`. For
  a line with `@name`, the mod reads `tribemod/bigdub/<name>.txt` (x y z yaw of the transform, the backdrop mesh name,
  the collide file name, the near-crowd actors to hide), passes the transform to `LoadLevelInstanceBySoftObjectPtr`
  (Location and Rotation, 7.1 of the load call), registers the named wall as the backdrop, hides the listed actors, and
  gives the walking map its transform. About 60 lines; the Halloween "screen name suffix" fix folds into it.
- EM_MAX 4 -> 8 (one define; the Halloween notes already asked for it); the menu then has room for "Big Dub",
  "Big Dub: Pavilion", "Big Dub: New Camp" next to the four boxes that exist. Whether Tribe's environment list shows 8
  boxes without scrolling is unknown: the first install checks it; if not, one box plus `tribemod/bigdub/active.txt`
  (a file the user edits, or the stage hop) selects the variant.

---

## 8. The show

### 8.1 Cue table and rows (bd_show.py)
`show.py`'s format: 32 bars x 16 rows at 140 BPM (54.86 s). Rows: main heads 0, wash 1, main fans 2-4, sky 5, pavilion
6, pavilion lasers 7, newcamp 8, newcamp lasers 9, lenses 10, hemlock 11, bridge 12, always 13 (camps, festoons, signs),
delays 14, eyes 15 (spare). Strobe always 0; the wash never pulses per beat. The program follows the mood table in section
3. `bd_cuecheck.py` is `hw_cuecheck.py` with the new material list.

### 8.2 Song mode, fader following, beat grid
The mod drives `MPC_DinoGiant` by a fixed path (**read**: dumper.cpp ~2480); the club plan's 5.6 asks for the lookup to
follow the active environment's collection. Big Dub ships `/Game/Mods/BigDub/MaterialInstances/MPC_BdShow` with the
same parameter names, so once that patch lands, song scripts, fader following and the beat-grid lock drive Big Dub
unchanged. Until then the show runs free on its loop.

### 8.3 The non-DJ walls
The two (or three) walls that are not Tribe's backdrop in a variant run `bd_materials.vj_wall`: a 4-slot flipbook of
procedural loops (tunnel, bulb ring, mushroom spore field, a text crawl of the stage name) switched per 8 bars by the cue
table, in the VJ palette, luma-capped at 70 percent like the loops. No video decoding is needed, and the walls read as
"another VJ is playing" from across the field.

### 8.4 Lasers over a slope
`laser_sweep` is unchanged; the clearance tool gains the terrain: each fan's lines are checked against the heightfield
and the near trees at 27 poses, landing points are set 2.5 m above the ground along the slope, and the Main Stage's
fans are aimed so they pass over the crowd bowl and land on the slope beyond it (a laser that sweeps along a hillside
reads from everywhere on the site; the overdraw and the 0.46 m gates stay).

---

## 9. Visuals wall

- The active variant's wall is `SM_Bd<Stage>Screen` with Tribe's back-wall UV layout; the mod registers it as the
  backdrop (7.5) and forces fill mode. The user's existing loop packs play as they are (the Dino and Halloween packs);
  Big Dub needs no new loops to ship.
- Later (decision 7): a Big Dub VJ pack (mushrooms, forest, creek, the circle's stones, the logo sting) at 140 half-time
  from the Visuals pipeline; the aspect is 16:9 on the Main and 2:1 on the Pavilion wall, so the pack is composed for
  the middle 90 percent as before.

---

## 10. Technical architecture

### 10.1 File layout (nothing shared is edited)

```
C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\bigdub\
  concept_blockout.py    the night blockout on the real terrain (done; run_concept.sh takes the GPU lock; sheet.py)
  bd_site.py             the generator: terrain tiles, creek, roads/splat, trees, camps, props, stones, sky, the four
                         stages (bd_stages\), crowds, bakes, FBX export, manifest, show groups, collide files
  bd_frame.py            the site frame, the three variant transforms, elev()/cls_at() over the geodata
  bd_kit.py              `from kit import *` plus: tent, canopy, vehicle, rv, hemlock, pine, oak, tree_card, festoon,
                         stone, bridge_segment, led_text (kit's font), mushroom, signpost, bell_tent, fire_card
  bd_stages\             bd_main.py bd_pavilion.py bd_newcamp.py bd_hemlock.py (set, rig, lasers, wall, deck, crowd
                         keep-outs), each with the research dimensions table at the top
  bd_show.py             the cue table (140 BPM); bd_collide.py (collide text + height.bin + the check image over the
                         site plan); bd_sky.py (star field for the date); bd_terrain.py (DEM -> tiles, splat, masks)
  checks\                bd_lasercheck.py (heightfield-aware), bd_overdraw.py, bd_cuecheck.py, bd_modlint.py
  out_bd\                bakes and FBX (BD_OUT=<dir>; --fast for the pipeline test)
C:\Users\Chris\TribeUE\TribeXR\Scripts\build_bigdub.py   UE import: /Game/Mods/BigDub, chunk 56 (PAL_BigDub), SURFACES
                         for every mesh, the terrain material, MaxDrawDistance per actor class, the three walls, deck
                         lamps per stage, BD_ANIM=1 for the fork-cooked animated build
C:\Users\Chris\TribeUE\TribeXR\Scripts\bd_materials.py   imports dino_materials; adds terrain_splat, water, tree_card,
                         vj_wall, festoon_flicker (the Halloween flicker), bridge_pulse, fire_card (Halloween's)
D:\TribeUE\MetaBigDub\TribeXR     the fork-project copy (like MetaHw / MetaClub), its own Saved\Cooked and ModPak,
                         Scripts\cook_bigdub.sh [build|cook|pack|all]
D:\TribeUE\bigdub_geo\            the geodata (Appendix B); read-only input to bd_terrain.py
C:\Users\Chris\TribeUE\paks_current\ + tribe hack\scripts\push_obb.sh      the only way to push (shared rule)
tribe hack\hook\                  no edits by this work: club.cpp / club_collide.h patches (7.2) and the env-menu patch
                         (7.5) are written to tribe hack\scratchpad\bigdub_patches\ and handed over
tribe hack\claudedocs\bigdub_stage_notes.md      this work's running log; NOTES.md stays the Dino session's
tribe hack\claudedocs\bigdub_concept\            the site plan, the hillshade, the blockout sheet
```

### 10.2 Build and ship (per iteration)
1. `blender -b --factory-startup --python bigdub/bd_site.py` under the GPU lock (`run_bd.sh`, the run_hw_stage.sh
   pattern). A full bake is ~25-35 min on the 1660S (estimate: Halloween's full v2 bake was 937 s with seven 4096 bakes;
   Big Dub has more surfaces but smaller ones). `-- --fast` is the 3-minute pipeline test.
2. `UnrealEditor.exe D:\TribeUE\MetaBigDub\TribeXR\TribeXR.uproject -ExecutePythonScript=build_bigdub.py -unattended
   -nosplash -nullrhi`, BD_ANIM=1 for the animated build (the terrain material, water, VAT crowds, lasers need the fork
   from day 1, unlike the other stages: the terrain material is the point of phase 0).
3. Cook with the fork: `-map=/Game/Mods/BigDub/Maps/Environment_BigDub`. First cook ~37 min (global shaders), then
   minutes. Grep the cook log for "Failed to compile" (the Halloween M_HwFire lesson).
4. `pack_chunk.sh 56` -> `pakchunk56-Android_ASTC_P.pak` with `ShaderArchive-TribeXR_Chunk56`.
5. `push_obb.sh --push --env "Big Dub=/Game/Mods/BigDub/Maps/Environment_BigDub@main" <pak>`: merges with the live OBB
   (today 50 + 53 + 54 + 55 = 412 MB, **measured** paks.txt 2026-10-09 17:19), refuses while Tribe runs. The OBB grows
   to ~670 MB; a stored zip has no limit that matters here, and the Quest has the space (assumed; `df` on the device at
   phase 0).
6. `tribemod/bigdub/main.txt` (+ pavilion.txt, newcamp.txt) and the collide files pushed via /data/local/tmp
   (`scripts/push_media.sh`'s method). Relaunch Tribe: paks mount at launch.
7. Device gate from logcat `[ENV]`, `[CLUB]`, `[PERF]`: load <= 3 s (bigger pak), the wall registers, walking map parsed
   with the heightfield, fps windows 71-72 standing at the decks and 71+ walking the whole site, no frame over 20 ms
   outside the load. The user confirms the pointer and a video on the wall.

### 10.3 Chunk and project copy
Chunks in use (**read** from the scripts and paks, 2026-10-09): 50 Dino and Festival, 51 ShaderTest, 52 MetaVat crowd
test, 53 DinoAnim, 54 Halloween, 55 club. **56 is free and taken for Big Dub.** The project copy goes on D: (C: is at
96 percent); the geodata already is.

### 10.4 The menu
`#define EM_MAX 4` (**read**, dumper.cpp 2121) and the headset's envs.txt is full (Dino Stage, Dino Classic, Reactor,
Graveyard Shift). Big Dub needs one to three boxes: EM_MAX 8 in the next mod build (the Halloween notes asked the Dino
session for the same line), or the user drops Dino Classic for now (one line; the level stays in chunk 53). Decision 2.

---

## 11. Performance: the big-site tactics and the phase-0 stress test

The Dino budgets (71-72 fps, ~600k tris, 32-41 actors, 0.57-1.0 layers/px overdraw) were set by what shipped, not by
what the Quest 3 can do. A walkable square kilometre changes two things: the tri count IN VIEW varies with where you
stand, and the actor count climbs past 40. So phase 0 ships a synthetic stress level first (terrain tiles with the real
material, 12k card trees, 900k unlit tris in view from the worst spot, 80 actors with MaxDrawDistance set) and measures
`[PERF]` standing and walking. The budgets below are targets to confirm or cut against on that result.

| budget | Dino (measured) | Big Dub target | tactic | how checked |
|---|---|---|---|---|
| fps | 71-72 | >= 71 at the decks, >= 70 anywhere on the site, 58+ streaming | per-actor MaxDrawDistance (near trees 220 m, cards 900 m, camps 400 m, props 300 m, other stages' rigs 350 m), region actors for frustum culling | logcat fps windows, a walk of the whole site |
| tris in view | ~600k always | <= 900k worst spot (the Main Stage looking down the site), ~500k typical | crowd tiers (6.5), card trees, terrain tiers, far silhouettes | bd_site.py per-mesh log + a view-cone estimator over the manifest |
| actors | 32-41 | <= 85 in the level, <= 45 drawn | region merging (9 regions), per-stage merged beams/halos/lasers | build_bigdub.py log; `[PERF]` draw count if the mod can read it (assumed not; fps decides) |
| translucent overdraw from the DJ | 0.57-1.0 | <= 2.0 | beams and halos per stage only within 350 m; water is opaque with emissive shimmer; no fog sheets on the open site | bd_overdraw.py |
| chunk size | 120-141 MB | <= 260 MB | terrain detail tiling instead of a 1 km albedo bake; 4096 bakes only for the core light map and the Main Stage; crowd VATs 2048 x 512 / 256 for the smaller crowds | pack_chunk.sh output |
| load time | 1 s | <= 3 s | | `[ENV]` log |
| walking | n/a | the flood fill reaches every lane; no stuck spots in the user's walk | the grid-accelerated map | tests/club_collide_test.cpp over the site; the walk |
| laser clearance | >= 0.46 m set, >= 4.9 m DJ head | same, plus terrain and trees | bd_lasercheck.py | |
| flashes | <= 3/s, no 1-frame hits | same | bd_cuecheck.py | |
| bake time | 18-19 min | <= 35 min | smaller bakes for props and camps (2048) | bake log |

If the stress test fails at 900k: first cut the far crowd tier density at the non-DJ stages, then card-tree count by
half beyond 300 m, then the mid ring's grid to 24 m. If actor count is the limit: merge the 9 regions into 4.

---

## 12. Phases, gates and parallelism (no stream date was given; each phase ends shippable)

| phase | work | gate |
|---|---|---|
| 0 Data, frame, stress test, walking on terrain | bd_frame.py and bd_terrain.py (DEM -> tiles, splat, masks, the three transforms); MetaBigDub on D:; chunk 56; the terrain material cooked by the fork; the stress level; the heightfield walking patch written against club_collide.h and tested with the flood fill on the Quest (tests/); envs.txt variant syntax patch written; the night sky for the date | the stress level holds 71 fps; the user walks the bare terrain from the plateau to the bridge site at 71+ fps and the slopes feel right in the headset; the Main Stage box sits at the origin in the "main" variant |
| 1 The site | creek, roads and festoons, trees (near/cards/far), camps and vehicles, props and landmarks (bridge, stones, gates, signs, labyrinth, altars), campers; MaxDrawDistance per class; first full bake | previews (aerial, each camp, the bridge, the gorge) approved in chat; fps gate walking the whole site with everything but the stages |
| 2 The Main Stage | bd_main.py from the research photos (Appendix D), rig, lasers over the slope, the wall as backdrop, crowd 2,200 with tiers and lanes, deck stairs, bd_show.py v1, the animated build | the stream shot and the crowd view approved; laser gates pass; comfort check passes; 71+ fps at the decks |
| 3 Pavilion, New Camp, Hemlock Hole + variants | the three other stages from the photos, their crowds, the VJ walls, the three variant files, near-crowd hiding, deck lamps per stage; the stage hop | each variant loads with its booth at the origin and its wall as backdrop; walking between all stages with no stuck spots |
| 4 Polish, media, reel | the user's walk-through notes (two iterations), the drone reel (Appendix A), the optional VJ pack, shuttle fast travel, the mod features installed in a combined APK with the other sessions' OK | a full dress rehearsal: a set on the Main Stage, a walk to New Camp during the breakdown, back by shuttle |

Parallelism: phase 1 runs as 3-4 agents (terrain + creek + roads; trees; camps + props; the checks and the collide
file), as the Dino and Halloween grounds did; phase 3's three stages are independent agents on one kit. Phases 0 and 2
are serialised on the frame, the generator and the fork cook. Rough calendar, assuming the GPU and the headset are shared
with the Dino, club and Halloween sessions until 2026-10-31: phase 0 one week, phase 1 one to two weeks, phase 2 one
week, phase 3 one to two weeks, phase 4 one week. Six to seven weeks of elapsed time, roughly mid to late November
2026, with the first walkable terrain in the headset inside the first week.

---

## 13. Decisions for the user (with recommendations; the plan proceeds on the recommendation if unanswered)

1. **Confirm the layout (section 1.4, reading D) from memory.** The Main Stage is the Stone Circle Stage (the guide's set
   times). The research places Camp Central, the Pavilion, the Stone Circle and Main Camp on the low tongue north of
   the creek's elbow, Hilltop and the Labyrinth on the big pasture, the Rainbow Bridge at the elbow next to the Hemlock
   Hole, and New Camp across the creek to the west. One look at `claudedocs/bigdub_concept/bigdub_site_plan.jpg`
   settles it. What only the user can add: which way the Stone Circle Stage faces, how far the stage sits from the
   stones, which bank the bridge lands on, and where exactly the New Camp Stage stands.
2. **Menu room.** Recommended: ask the Dino session for EM_MAX 8 in its next build. Alternative: drop Dino Classic's box
   for now.
3. **Variants.** Recommended: one level loaded at three transforms (three boxes: Big Dub, Big Dub: Pavilion, Big Dub: New
   Camp). Alternative: three cooked maps; or one box plus the stage hop only.
4. **Hemlock Hole Stage.** Recommended: build it as the light fourth stage (no DJ variant). Alternative: skip it, or make
   it a fourth variant.
5. **Night, and which hour.** Recommended: the Main Stage variant at 22:30 (the real headliner hour at the Stone Circle:
   the Milky Way core due south, the gibbous moon up) and the Pavilion and New Camp variants at 01:00 (their real
   after-hours), one sky texture each. Alternative: one 01:00 sky for all three, or a dusk variant later.
6. **Shuttle fast travel.** Recommended: yes, at the four real stops. Alternative: run only.
7. **A Big Dub VJ pack.** Recommended: after phase 3, not on the critical path. The existing packs play from day 1.
8. **Exactness vs. budget for the camps.** Recommended: 700 tents / 260 vehicles at the map's densities. Alternative: half,
   if the stress test says so.
9. **Branding and the Main Stage's year.** Recommended: the 2026 design (LED pillars out in the crowd, the lit sun
   emblem, jellyfish and spiky flowers in the trees), the real names, a hand-painted version of the swirling BIG DUB
   lettering with mushrooms on the gate, the banners and the signs, Kikiwawa the mascot among the inflatable mushrooms
   of Mushroomland. Alternative: the 2023 look with the painted knotwork serpent facade, or a stylised "BIG DUB" in the
   kit font only.

---

## 14. Risks, ranked (probability x cost x silence)

1. **The walkable site costs frames: tris in view, actors, alpha-tested cards.** Silent in previews, loud on device.
   Mitigation: the phase-0 stress level before any content; per-class MaxDrawDistance; the cut order in section 11.
2. **The level-instance transform route breaks something Tribe anchors to the level origin** (the backdrop registration,
   the spectator cameras, the lift's MPC lookups, the drone path). Mitigation: phase 0 loads the bare terrain at the
   "main" transform first; the fallback (three cooked maps) needs no hook change for the load.
3. **The heightfield walking patch** is the biggest change to the club's files yet (new floor type, limits, a grid).
   Mitigation: the rules stay engine-free in `club_collide.h` and the flood-fill test runs on the Quest before any APK;
   the patch is handed to the club session as a file plus the test's output, and the APK is built by whoever builds next,
   with the Dino and club lines kept (the 2026-10-09 memory rule).
4. **Research gaps make tier B guesses** (the Pavilion's size, the Main Stage's real design, the bridge). Mitigation:
   every tier-B size is marked and lives at the top of its stage module; the first headset look at a stage is on
   its blockout box before its detail is built.
5. **OBB and menu coordination with three other sessions** (a push that drops a pak, a re-seed with a stale envs.txt,
   the four-box cap). Mitigation: push_obb.sh only, both envs.txt copies, EM_MAX 8 asked for now.
6. **Pak size and load time** (~260 MB; the OBB at ~670 MB). Mitigation: the detail-tiling terrain, 2048 bakes for
   everything but the core light map and the Main Stage, VAT sizes per crowd; measured at phase 1's first cook.
7. **The far crowd up close** (walking through 21-tri people). Mitigation: the walk-lane mid-tier rule and the lanes.
8. **The 1 m DEM is bare earth from 2019; the festival's 2026 grading, new buildings (the Pavilion?) and the bridge are
   not in it.** Mitigation: tier B photos override the data locally (a platform cut for a stage is a few lines).
9. **Imagery licensing.** Esri tiles are reference only; nothing from them ships; the DEM is public domain; OSM is ODbL
   (attribution in the notes file). No downloaded photo ships either.
10. **Comfort on a slope**: walking down an 8 percent grade in VR moves the horizon. Mitigation: the walking code already
    eases height changes (0.2 s); a comfort vignette option if the user asks; run speed off by default downhill.
11. **Time: the headset and GPU are shared with three sessions until Halloween ships.** Mitigation: phases end shippable;
    phase 0's stress test and terrain walk are the only device slots asked for before 2026-10-31.

---

## 15. Working next to the Dino, Halloween and club sessions

| shared thing | hazard | rule |
|---|---|---|
| the patch OBB | a push that lists only some paks drops the others, silently | `paks_current` + `push_obb.sh` only; the merge keeps 50/53/54/55 |
| `hook/dumper.cpp` (Dino), `hook/club.cpp` + `club_collide.h` (club) | three editors on two files | Big Dub writes patches to `scratchpad\bigdub_patches\` with the test output; applied by the owners at a quiet point; one combined APK per install, keeping every session's lines |
| the GPU (1660S) | bakes collide | `gpu.lock.d`; Halloween first until Oct 31; Big Dub bakes in the gaps (the blockout already used the lock) |
| the headset and the tester | every device gate needs the user | one Big Dub device test per day before Oct 31 (the stress level, then the terrain walk), batched with a pass/fail list |
| `tribemod/envs.txt`, `backup/tribemod_20261006/envs.txt`, reseed.sh | a re-seed restores a stale list; the 4-box cap | append in both places; never write into the backup while a re-seed runs (the 2026-10-09 lesson); EM_MAX 8 requested |
| kit.py, show.py, crowd3.py, dino_materials.py, build_dino.py | contract drift | import only; start-up assertions; adapt on our side |
| Halloween and club files | none if untouched | never edited; their methods are copied (cuecheck, overdraw, collide, ship script) |
| NOTES.md | concurrent edits | Big Dub logs to `claudedocs/bigdub_stage_notes.md` |

---

## Appendix A. Drone reel draft (tribemod/drone_path.txt syntax; world cm in the "main" variant: the DJ at the origin facing -Y)

The site frame maps to the main variant by: the DJ faces west, so Dino X = crop y - 130 (south is the DJ's left, +X)
and Dino Y = crop x - 1210 (the crowd toward -Y = west, the knoll's east end and High Meadow behind at +Y); z =
elevation - 253.5. In that frame (metres): the stones ring the origin at 24-30 m; the knoll's flat top runs to y -60
at z -1; the Pavilion and Camp Central are ahead at (-54, -138), z -6; the Village Green and parking ahead-right at
(-50, -75); North Crook ahead-right at (-130, -280), z -24; the Big Bottom's campfires ahead-left at (+150..+390,
-250..-50), z -22; High Meadow behind-left at (+300, +190), z 0; White Pines at (+430, -70), z -24; the Hemlock Hole
at (+420, -20), water z -27; the bridge at (+470, -100), deck z -18; the New Camp Stage at (+520, -150), z -10; the
Labyrinth at (+670, -63), z +22; the farmhouse at (+1150, -126), z -23. (Ground heights from the DEM; the reel is
re-aimed against the built modules with the drone-check tool.)

```
# ridge reveal: from over Hilltop, the tongue below with its bowl of lights, the stage glow among the stones ahead
fly 14 60000,-12000,9000 22000,-5000,4000 look=0,0,1500
# up the Big Bottom's slope at head height toward the stage, campfires passing, trunks either side
fly 16 25000,-15000,-2000 6000,-5000,-200 look=0,0,900
# through the stones, the stage behind them
fly 12 -3200,-2600,150 -1400,-900,300 look=0,0,1200
# over the crowd to you
fly 14 0,-6000,900 0,-700,330 look=dj
# close orbit around you
orbit 15 r=260 h=30 deg=360 start=-90
# over your shoulder: the crowd, the Pavilion's glow at the far end, North Crook's creek beyond
fly 8 -250,380,260 250,380,260 look=-5400,-13800,-500
# the pavilion and Camp Central, close
fly 10 -2000,-9000,600 -4500,-12500,300 look=-5400,-13800,-400
# down the Big Bottom to White Pines, campfires and vendors lit
fly 14 12000,-6000,-1800 36000,-6000,-2300 look=43000,-7000,-2400
# the Hemlock Hole from above and its stage on the beach
fly 12 38000,-5000,-1400 43000,-2500,-2200 look=42000,-2000,-2700
# the rainbow bridge, crossing it south
fly 12 46000,-10000,-1400 48500,-10000,-1500 look=52000,-15000,-1000
# New Camp's stage on the neck under the trees
fly 10 50000,-13000,-900 52500,-15500,-800 look=55000,-19000,-1000
# crane up and back to the stage glow on the knoll
fly 14 50000,-14000,-500 15000,-6000,2500 look=0,0,1500
```
About 163 s. Cuts on change; eased with smoothstep (the mod's path mode). Checked with the Halloween drone-check method
once the modules exist.

## Appendix B. The geodata folder (`D:\TribeUE\bigdub_geo\`)

| file | what | source / licence |
|---|---|---|
| data/dem_x72y441.tif | USGS 1 m DEM tile, 10 x 10 km, EPSG:26917 | USGS 3DEP, public domain |
| dem_crop.npy, dem_crop.json | the 2,000 x 1,800 m float32 crop (rows = y south, cols = x east) and its origin | derived |
| dem_hillshade.png | hillshade + 5 m contours + OSM lines, 1 px = 1 m | derived |
| data/overpass.json | OSM ways/nodes in the bbox (roads, creek, woods, buildings) | OpenStreetMap, ODbL |
| creek_roads_diagram.png | the creek (with node indices) and roads on a 100 m grid | derived |
| aerial_z17*.jpg, aerial_z19*.jpg, data/tiles*/ | Esri World Imagery mosaics (0.92 and 0.23 m/px) with OSM overlays and a 100 m crop-frame grid | Esri; reference only, never shipped |
| masks.npz, masks_preview.png, masks.py | 2 m land-cover classes (field / deciduous / evergreen / water / road), the creek polyline and roads in crop metres | derived |
| landmarks.json, agent_landmarks.json | landmark coordinates (the first table of 2026-10-09 afternoon; the grounds agent's coordinates converted) with UTM, lat/lon and elevation | derived |
| flow_acc_ha.npy, creek_path.json, creek_channel.json | D8 flow accumulation (2 m cells, hectares) over the crop and the creek's main stem in downstream order with water elevations | derived (flow.py) |
| elev_classes_*.png, dem_local_relief*.png, zoom_*.jpg, clean_*.jpg, aerial_z19_tongue*.jpg, aerial_z19_peninsula*.jpg | elevation-class and contour renders, LiDAR local relief, gridded 0.23 m/px zooms of the tongue, the knoll, the elbow and the creek reaches | derived / Esri reference |
| site_plan_v3.png / .jpg (+ v2) | the layout drawn on the aerial, reading D refined (also in claudedocs/bigdub_concept/) | derived |
| ref/grounds/ (129 files + manifest.md), ref/stages/ (78 files + manifest.md + report.md), ref/video/ (frames from the 2026 flyover and the 2014 drone video + README.md) | the research agents' reference photos, maps, PDFs and video frames with their sources | copyrighted, reference only, never shipped |
| landmark_sheet.jpg | six zoomed aerial crops of the landmarks | Esri, reference |
| site_plan.png / .jpg | the layout drawn on the z19 aerial (also in claudedocs/bigdub_concept/) | derived |
| festmap_*.png | quadrant crops of the official map for study | the festival's map |
| overlay.py, dem.py, creekdiag.py, z19.py, stitch19.py, site_plan.py | the scripts that made the above (system Python: numpy, PIL, tifffile, imagecodecs, pyproj, scipy) | |

bd_terrain.py reads only dem_crop.npy, dem_crop.json, masks.npz and landmarks.json.

## Appendix C. Budgets at a glance

| item | estimate |
|---|---|
| terrain | 270k tris (90k in view), 1 light map 4096 + 1 at 2048, splat 2048, 4 detail tiles 1024 |
| trees | 1,800 near (470k total, ~120k in view), 12k cards (48k), 20k far silhouettes (one draw); atlas 2048 |
| camps | 700 tents, 260 vehicles, 180 canopies: ~140k tris, 2 bakes 4096 |
| props and landmarks | ~90k tris, 2 bakes 2048 |
| stages | Main set+rig ~70k, three smaller ~35k each; bakes 4096 (Main) + 2048 x 3 |
| crowds | 3,600 festival-goers + 300 campers: ~420k tris in the Main variant; VATs 2048 x 512 + 3 x 2048 x 256 |
| pak | <= 260 MB |
| actors | <= 85 in the level, <= 45 drawn |

## Appendix D. Research findings on the real stages and grounds

Reference material lives OUTSIDE the repo (downloaded, copyrighted, reference only): `D:\TribeUE\bigdub_geo\ref\grounds\`
(129 files + `manifest.md` mapping each file to its source URL).

### D.1 Read directly (2026-10-09)

| item | finding | source |
|---|---|---|
| Stage set | four stages every year since at least 2025: Stone Circle (main), Pavilion = "HiScore" in the schedule, Hemlock Hole, New Camp | guide 2026 pp. 8-11; 2025 and 2026 maps |
| Main Stage hours | Stone Circle 2-3 PM to 11 PM-12:15 AM (headliners); Pavilion/HiScore to 4 AM; Hemlock Hole to ~4:30 AM; New Camp to ~4 AM | guide pp. 8-11 |
| Stone Circle | 61 m (200 ft) diameter, 60+ standing stones, two-thirds of the ring standing, on a hilltop, raised by hand since 1995 | guide p. 7 |
| Camp Central | the Coffee Dragons Cafe + the Information Booth + the upper shower house; the Farmhouse Office is the sanctuary office | guide pp. 5-6 |
| Place names | North Crook (second shower house, shuttle stop), White Pines (security hub, shuttle stop, White Pines Loop), the Big Bottom (EMS), the Mountain (fire spinning, theme camps), the Seminar Stage (EMS hub in Main Camp), the Drum Circle | guide pp. 4-6, 12 |
| Pavilion | timber-frame hall, posts with knee braces, exposed trusses, boarded ceiling; HiScore game lounge inside | photos 2023_306, 2023_416 |
| Rainbow Bridge | cable-stayed timber footbridge ~40 m over a calm 25-30 m reach; swimmers below | drone frames t012, t162, t168 |
| Hemlock Hole | wide slow pool, gravel beach, hundreds of swimmers and floats | drone frame t141 |
| Labyrinth | a mown circle with a yellow inflatable at its centre, in a field with RVs, a school bus (the shuttle), rows of parked cars and a road fork, small buildings at the field's north end | drone frames t066, t084 |
| Main Stage look | forest stage: tall trunks in the crowd, wide LED wall, tall LED pillars with the spiral motif, truss roof, green laser fans, purple wash | landing-page hero photo (2026 on-sale banner) |
| Frick Frack Blackjack | red/white striped big top, string lights, green felt table, carnival props | photos 2023_616, photo1, photo4, eliyahu_263 |
| Camps | UV stretch fabric (Illuminarium), an LED pixel wall in the woods, a parachute game, yoga in the woods, "Camp Clown-A-Round", "Follow the White Rabbit", "gRaveYard Smash", "Camp Portal", "Camp Truffle", "The Stoop" (90s theme), "The Sauce Sanctuary", "Disco Den", "Scratch Camp" (DJ battles, open decks), "The Expanse" (wellness) | guide pp. 12-13; photos |
| Fairview Station | a large parking field in rows next to a green-roofed house and a cleared slope, with a barn and mown fields beyond | drone frames t207, t213 |
| Four Quarters | "over 200 acres", "an enclosed river valley bisected by Sideling Hill Creek ... creek-side pools to dry cliff face, mature forest to hilltop meadow"; a 400 ft deep well (2017); Stones Rising every September | guide pp. 6-7, 36 |

### D.2 The research agents
- **Grounds (done, 2026-10-09 23:20):** 129 reference files + `manifest.md` in `D:\TribeUE\bigdub_geo\ref\grounds\`;
  the full report is `claudedocs/bigdub_research_grounds.md`; the facts are folded into sections 1.3, 1.4, 1.5, 5.6,
  5.7 and 6, and summarised in D.3.
- **Stages, first attempt (failed):** hit its session limit before writing anything.
- **Stages, second attempt (done late 2026-10-09):** 56 video frames + 22 site files + `manifest.md` + `report.md` in
  `D:\TribeUE\bigdub_geo\ref\stages\`; the report is copied verbatim as `claudedocs/bigdub_research_stages.md` and
  condensed in D.5. Its main negative result: no production vendor (sound, lighting, lasers, LED, staging, design) is
  credited anywhere reachable, so the stage kits are built from the photos alone.

### D.3 Grounds research, condensed (full text in bigdub_research_grounds.md)

| topic | finding |
|---|---|
| the site | a horseshoe bend of Sideling Hill Creek through Town Hill; 200-300 acres; creek 757 ft at the inflow to 709 ft at the outflow; "more than a mile and a half of graveled roads" |
| the layout | reading D of section 1.4: Camp Central (Coffee Dragons, Upper Shower House, kitchen, dormitory) at the tongue's north tip by the North Crook hairpin; the Pavilion on the slope above the creek next to it; the Stone Circle in the tongue's woods (+/-120 m); the Big Bottom, Main Camp, High Meadow and White Pines on the tongue; the Hemlock Hole at the elbow with the Rainbow Bridge beside it; the Old Forest and New Camp west of the creek with their own PA 26 gate; Hilltop, Main Parking, RV Land and the Labyrinth on the pasture; the farmhouse cluster = Camp Office and Main Registration |
| Stone Circle | 200 x 160 ft ellipse turned 12 degrees west of north; 60+ sandstone slabs (10,000-14,000 lb, up to 14 ft), two-thirds standing; Flame Stone 22 ft in the north, Mother Stone 13 ft with an 18-inch portal, West Gate pair with a 20 ft gap, the North Copse inner ellipse; bare dirt floor, log benches, North Altar, tall straight hardwoods; the biggest stage stands inside it |
| Pavilion | "New Dance and Dining Pavilion" 2010, 70 x 30 ft, timber post-and-beam with arched knee braces, open sides with a rail, deck on concrete piers, green standing-seam gable roof, sprung dance floor; HiScore inside |
| Hemlock Hole | 25-30 m tea-coloured pool, shale cliff outside the bend, gravel beach inside, hemlocks; one of six holes (Stone Ledge, Big Pool, North Crook are others) |
| Rainbow Bridge | 2018-19 suspension footbridge: steel pylons, main cables and hangers, 1.5 m plank deck, chain-link mesh side panels, deck sag, 8-10 m above the pool, 60-70 m long (inferred); "a walk through the tree tops" |
| Labyrinth | 76-84 ft modified Cretan 7-circuit on the Hilltop, granite curbs, mown circuits, four solstice poles, solar lights; the mascot balloon in its centre at Big Dub 2026 |
| Fire Circle | the Upper Fire and Drum Circle: 85 ft sand ring, 75 ft timber arbor, 46 ft open centre; flame jets at Big Dub |
| other permanent structures | Starvin' Artist kitchen, Old Kitchen Pavilion, a 24 x 24 ft stage, Elder dormitory, Ceremonial Shed, Upper and Lower Shower Houses, Coffee Dragons' Lair (a shaded deck), Members Camp tent platforms, sweat lodges, the Fairy Cairn, four slab altars, the c.1890 farmhouse, the Loft & Shop, a winery |
| vegetation | tall straight oak and tulip over the circle, hemlock along the creek, white pine copses, mown hay fields, scrub meadows with small conifers, shale cliffs on the outsides of bends |
| unknowns | the circle's exact centre and stone layout; the bridge's length and landings; the Main/New Camp boundary at the elbow; creek width; pavilion pitch and post spacing |

### D.4 The stages, from the photos and frames (read 2026-10-09; files in ref\grounds\)

| stage | what the pictures show | files |
|---|---|---|
| Stone Circle Stage (main) | a stage set among tall straight trunks that stand INSIDE the crowd; a wide bright LED wall centre; tall LED pillars/panels flanking it and standing out in the crowd; a glowing sun-ray or mushroom emblem above the wall; a truss roof with two rows of moving heads (red power LEDs by day); laser fans from several points (the roof, the pillars, towers at the crowd's sides) in cyan, white and green at night, purple/pink in older years; purple wash and haze; inflatable sculptures hung in the trees (white spiky flowers, a yellow jellyfish) and fabric streamers in the canopy; 10 x 10 canopy tents at the crowd's edges; dense crowd of 1,500-2,500 | stone_circle_stage_night_lasers_crowd_aftermovie2026_t148, forest_stage_daytime_crowd_led_panels_recap2025_t040, forest_stage_night_lasers_tall_trees_bigdub, forest_stage_night_lasers_recap2025_t136, landing-page hero |
| Pavilion / HiScore | inside the timber hall: posts with knee braces, trusses, a boarded ceiling, string lights and small par cans on the beams, Nintendo-character cutouts, hanging flowers, big screens on the side walls, benches, consoles; packed at night under warm light | pavilion_interior_night_timber_posts_bigdub2023, stage_night_crowd_under_lights_aftermovie2026_t052, bigdub_photo_2023_306 |
| the smaller forest stages (Hemlock Hole / New Camp) | a low deck with a truss frame, a white fabric projection screen as the backdrop (not an LED wall), PA stacks on truss either side, a painted banner on the booth front, trees behind; an older frame shows a blue canopy-roof stage with a crowd barricade | forest_stage_daytime_djs_trees_backdrop_bigdub, stage_truss_roof_in_forest_drone2014_t480 |
| the Frick Frack tent | a red-and-white striped big top with string lights, a green felt blackjack table, carnival props, giant playing cards | bigdub_photo_2023_616, photo1, photo4, eliyahu_263 |
| camps and art | an LED pixel wall in the woods, UV stretch fabric, a parachute game, yoga in the woods, hammocks at the circle's edge | bigdub_photo_fb_67780052, fb_385914044, dsc1776, dsc2636, stone_circle_edge_hammocks |

Consequences already applied: the Main Stage kit (6.1) is a forest stage with LED pillars, inflatables in the trees
and laser sources out in the crowd; the two smaller stages (6.3, 6.4) get a white projection screen backdrop driven by
the VJ-wall material (and, in their DJ variants, Tribe's video on a 4:3-ish white screen) instead of an LED wall; the
Pavilion's interior is the HiScore lounge.

### D.5 Stage research, condensed (full text in bigdub_research_stages.md; frames in ref\stages\)

| topic | finding |
|---|---|
| production credits | none found anywhere: not on the site, in the 2025 program or the 2026 guide, in press, or in the video descriptions. Known: the organisers are "the founders of Nightmare Festival and Dreamscape Festival", general manager John Normoyle (2022); the 2023 recap was produced by Brand1Films; 2014 stage deco by Nephilnine, installations by Dancing Zombies and Slow Kidz (UV mushrooms, fibre-optic flowers), lighting by "Sentient Lighting"; 2016 floating jellyfish by Madison Pollard (12 ft, PVC, umbrellas, LEDs). Photographers: Elliot Kerachsky, Justin David, BassFace Nation, Soph Shull, Chopped Dubs, Mako Photo, Grayson Hall, Zoophoria |
| Stone Circle Stage 2023 | raised deck under a flat box-truss roof (front truss with moving heads and blinders); centre LED wall behind the booth; one portrait LED panel each side hung in front of the trees; a tall painted facade of psychedelic knotwork serpent/dragon art in orange-pink-purple flanking the whole stage; a silver sun/gear emblem on blue fabric centred on the truss; flown line arrays plus ground subs; barricade; red/pink stretch-fabric shade sails overhead; dirt floor with live trees inside the audience; wooden benches; red laser fans and green laser arcs at night |
| Stone Circle Stage 2024 | centre LED wall with red/white spiral graphics; four portrait LED pillars (two per side) playing the same spirals; truss roof with moving heads; purple wash; green laser fans from above and behind the stage; trees in the crowd |
| Stone Circle Stage 2025 | box-truss roof with moving heads, blinders and strobes; centre LED wall; two tall portrait LED panels on scaffold towers flanking the stage plus a second pair further out among the trees; black PA stacks; a low deck; purple wash, white laser fans; white spiky "flower" inflatables in the trees; flame-effect fireballs |
| Stone Circle Stage 2026 | centre LED wall about three panels wide; two tall LED pillars each side near the stage plus at least three more per side out in the crowd; a glowing sun/flower emblem with rays above the wall (the 2023 silver sun, now lit); laser fans from both sides crossing over the crowd (cyan/white, red+purple, green); blue inflatable jellyfish and white spiky flowers hung in the trees; heavy haze; purple wash. Close-up: the booth front is itself an LED panel; the top truss carries about eight moving heads plus LED batten/strobe bars |
| Pavilion / HiScore | "over 300 games with 18 consoles", bracketed tournaments, cosplay pageants; exposed timber frame with arched braces; long strands of artificial wisteria hanging from every rafter; red/pink/purple uplighting; rows of gaming tables with monitors down the middle; Mario-universe cutouts (older) and purple cartoon astronaut/raver cutouts (2026); the DJ booth at the far end under the arches, its sides dressed with ornate carved-look panels (2024); flat screens on the walls; glowing paper-lantern "planet" spheres in the trees outside (2023) |
| the small truss stage with sea creatures | a ground-support "goal-post" truss stage (two towers and a top truss with moving heads), a purple-pink inflatable octopus on top of the truss, inflatable jellyfish (pink, yellow, green, cyan) in the surrounding trees, a green neon dinosaur on a tower, a canopy tent beside it, a barricade (2024, 2025). Which stage it is (Hemlock Hole or New Camp) is NOT confirmed; the plan gives the sea-creature decor to Hemlock Hole (the swimming hole) and keeps New Camp plain until a photo says otherwise |
| other lit structures | the Fire Circle (round fenced arena, central fire, fire performers); the Frick Frack striped tent; an inflatable serpent arch over a path with a purple-lit canopy; illuminated green rings; MUSHROOMLAND: giant inflatable red-capped white-spotted mushrooms about twice human height and pink/purple inflatable flowers, with the mascot among them |
| the mascot | KIKIWAWA: a yellow egg-shaped inflatable two to three people tall with black double-spiral eyes, a wide smiling mouth with a pink tongue, stubby arms and feet and a tuft of green leaves on top; present every year 2023-2026; damaged by the 2025 thunderstorm; the 2026 aftermovie's plot is a reporter searching for it |
| branding | "BIG DUB" in ornate swirling psychedelic lettering with FESTIVAL in small caps beneath, spirals inside the letters and a spiral finial; the 2026 cover frames it with red-capped mushrooms and daisies; the spiral motif is reused as LED content |
| festival facts | attendance unofficial, "around 4,000 a year" to "5,000"; Big Dub 2027 is July 20-25; Lil Dub (a "Big Dub Re-Union") Sept 25-27 2026; theme camps since 2012; stage names 2016: Stone Circle, Pavilion, Hemlock Hole, Hilltop; 2019: plus Old Forest, Pirate, North Crook; 2025-2026: Stone Circle, HiScore, Hemlock Hole, New Camp |
| theme days 2026 (read from the poster `ref/stages/site/BIG-DUB-2026-FULL_1080x1080.jpg`) | Thursday PAJAMA JAM (jammies, onesies, face masks); Friday UNDER THE SEA (mermaids, pirates, beach bums, SpongeBob cosplay); Saturday SPACED OUT SATURDAY (astronauts, aliens). The poster shows Kikiwawa in all three costumes. Consequence for the crowd (section 6): the headliner night is Friday, so the Main Stage variant's crowd gets an under-the-sea costume layer (mermaid tails, pirate hats, inflatable sharks and jellyfish totems) on top of rave attire, and the octopus/jellyfish stage decor and the sea-creature theme camps fit the whole festival, not one stage; a Saturday variant would swap in astronauts and aliens (the Pavilion's 2026 astronaut cutouts) |
| food vendors 2025 | Wok N Tok, Naders Bistro, Sassy Wraps, Puttin' on the Mitts, plus the Coffee Dragons cafe (2026 list not found) |
| unknowns | every production vendor; any LED or stage dimension; which stage carries the sea creatures; the New Camp Stage's look; official attendance |
