"""REACTOR layout: the one source of the club's dimensions (claudedocs/club_venue_plan.md section 3, tribe hack repo).

Frame (the Dino frame): meters, Z up, the DJ at the origin facing -Y (the crowd), the core bay behind the DJ (+Y). The
stage deck IS Tribe's floor (z 0); the dance floor is FLOOR below it. Unlike the Dino Stage there is no stage drop: the
club is modeled where it ships. club_stage.py (the bake), club_collide.py (walking, phase 2) and the checks import this;
concept_blockout.py keeps its own copy of the numbers (it predates this file).
"""
FLOOR = -1.2                                   # dance floor top
HX = 12.0                                      # hall interior half-width (x -12..12)
Y_BACK, Y_SCREENWALL, Y_BAY = -30.5, 5.5, 13.0 # back wall (bar side), screen wall line, core bay back wall
CEIL, STAGE_CEIL = 9.8, 12.8                   # ceiling over the floor / over the stage house and the core bay
LIP_Y = -3.0                                   # stage lip; the proscenium header steps the ceiling up here

SCREEN_Y, SCREEN_HW, SCREEN_Z0, SCREEN_Z1 = 5.4, 8.0, 0.5, 9.5     # main screen: 16 x 9 m (16:9), the core window
FRAME_W = 0.6                                  # hazard frame around the main screen
SIDE_C = ((-9.6, 0.6, 3.7), (9.6, 0.6, 3.7))   # side screens: centres; 6 x 3.375 m, turned to face (0, SIDE_AIM_Y)
SIDE_HW, SIDE_HH, SIDE_AIM_Y = 3.0, 1.6875, -12.0

BARRIER_Y = -3.6                               # crowd barrier in front of the lip, x -8..8, 1.1 m high
STAGE_HW = 8.0                                 # stage proper x -8..8; wings x 8..12 either side at the same height

MZ_X0, MZ_X1, MZ_Y0, MZ_Y1, MZ_Z = 8.0, 12.0, -24.0, -8.0, 2.3    # mezzanines (both sides): x +-(8..12), deck top z
MZ_STAIR_Y0 = -30.0                            # mezzanine stairs along the side walls: y -30 (floor) .. MZ_Y0 (deck)

AIR_X0, AIR_X1, AIR_Y0, AIR_Y1 = -12.0, -8.0, -5.6, LIP_Y      # the airlock vestibule (the stage gate); stairs inside
DOOR_X0, DOOR_X1, DOOR_TOP, LINTEL_TOP = -11.2, -9.0, 1.4, 2.4
DOOR_MID = (DOOR_X0 + DOOR_X1) / 2
STAIR_N, STAIR_Y0 = 7, -5.1                    # 7 steps of (0 - FLOOR) / 7 = 17 cm from y STAIR_Y0 up to the wing at LIP_Y

TRUSS_Y, TRUSS_Z = (-6.0, -12.0, -18.0, -24.0), 8.6                # hall trusses (x -11.4..11.4)
FRONT_TRUSS = ((-9.5, -1.5, 8.8), (9.5, -1.5, 8.8))               # front-of-stage truss: the laser bar
BAY_TRUSS = ((-9.0, 3.0, 10.6), (9.0, 3.0, 10.6))                 # core-bay truss
COL_Y = (-30.0, -24.0, -18.0, -12.0, -6.0, -3.0)                  # wall columns (none on the airlock side at -6, -3)

VESSEL_X, VESSEL_Y, VESSEL_R, VESSEL_TOP = 0.0, 9.4, 3.2, 9.6     # reactor vessel; dome z scale 0.8 -> top ~12.2
TOWER_X, TOWER_Y = 6.6, 10.6                                       # control-rod drive towers at x +-6.6

BAR_X0, BAR_X1, BAR_Y = -7.0, 3.0, -27.5                           # COOLANT BAR counter; back bar at Y_BACK
EX0, EX1, EX_H, EX_DEPTH = 5.0, 8.0, 3.0, 5.0                      # entrance in the back wall + decontamination corridor

TABLE = {"x0": -0.95, "x1": 0.85, "y0": -0.05, "y1": 0.50, "top": 0.74}   # Dino's booth table under Tribe's gear
DJ_EYE = (-0.1, 0.9, 1.68)                                         # PlayerStartDJ (-6, 87, 1) cm + eye height
ROD_X, ROD_Y = 3.0, 0.6                                            # "control rod" light columns at x +-3 (outside the
                                                                   # SpectatorBoundingBox x +-2.5)
# Tribe's SpectatorBoundingBox (world cm, Session 3t): keep set geometry out of it, the deck floor aside
SPECTATOR_BOX = ((-2.5, -2.21, -0.06), (2.5, 2.79, 4.94))
