"""Where the REACTOR crowd stands: one list for the bake (club_stage.py hands it to club_crowd.build_crowd2 as `points`)
and for walking (club_collide.py turns each person into a soft `person` the hook wades through). Plain Python (no bpy);
the same seed gives the same list to both.

v2 (2026-10-09, the user: "have more people in the crowd" and "be able to walk in the crowd"): ~320 people, packed at the
front, two rows deep on both mezzanine rails, the bar's hall side, a thin fringe in the side aisles. The aisles between
the dance floor and the mezzanine supports stay open as walkways (to the airlock, the bar and the stairs)."""
import math

import club_layout as L


def _face(x, y, tx, ty):
    """crowd3's yaw (0 faces +Y) for someone at (x, y) facing (tx, ty)"""
    return math.atan2(-(tx - x), ty - y)


def club_points(rng):
    """(x, y, zone, floor z, yaw or None) in the club frame (Blender m). zone picks the dances (club_crowd.CLIP_ZONE):
    front / middle / back on the dance floor, rail on the mezzanines, bar at the bar. yaw None = face the stage (the
    crowd generator's own rule, with a little scatter); the floor z is absolute."""
    out = []
    y = L.BARRIER_Y - 0.6                                               # the dance floor, x -7.3..7.3
    while y > -18.5:
        zone = "front" if y > -8.0 else "middle" if y > -13.0 else "back"
        sp = {"front": 0.80, "middle": 0.90, "back": 1.02}[zone]
        keep = {"front": 0.95, "middle": 0.90, "back": 0.85}[zone]
        x = -7.3 + rng.uniform(0, sp)
        while x < 7.3:
            if rng.random() < keep:
                out.append((x + rng.uniform(-0.12, 0.12) * sp, y + rng.uniform(-0.12, 0.12) * sp, zone, L.FLOOR, None))
            x += sp * rng.uniform(0.92, 1.08)
        y -= sp * 0.92
    y = -19.3                                                           # the back floor, thinner
    while y > -24.5:
        x = -7.0 + rng.uniform(0, 1.5)
        while x < 7.0:
            if rng.random() < 0.5:
                out.append((x + rng.uniform(-0.3, 0.3), y + rng.uniform(-0.3, 0.3), "back", L.FLOOR, None))
            x += 1.5
        y -= 1.4
    for sx in (-1, 1):                                                  # a thin fringe in the side aisles, by the lounges
        y = -8.8
        while y > -22.0:
            if rng.random() < 0.3:
                px = sx * rng.uniform(8.8, 9.8)
                out.append((px, y + rng.uniform(-0.3, 0.3), "back", L.FLOOR, _face(px, y, 0, 3) + rng.uniform(-0.6, 0.6)))
            y -= 1.2
    for sx in (-1, 1):                                                  # the mezzanine rails, two rows deep
        for row, (x0, x1, keep) in enumerate(((L.MZ_X0 + 0.6, L.MZ_X0 + 1.1, 0.85), (L.MZ_X0 + 1.6, L.MZ_X0 + 2.2, 0.45))):
            yy = L.MZ_Y1 - 0.8 - 0.4 * row
            while yy > L.MZ_Y0 + 0.6:
                if rng.random() < keep:
                    px = sx * rng.uniform(x0, x1)
                    out.append((px, yy, "rail", L.MZ_Z, _face(px, yy, 0, 2)))
                yy -= rng.uniform(0.9, 1.15)
    for k in range(12):                                                 # the bar: by the stools, facing the back bar
        if rng.random() < 0.85:
            out.append((L.BAR_X0 + 0.4 + k * 0.85 + rng.uniform(-0.1, 0.1), L.BAR_Y - 1.45 + rng.uniform(-0.1, 0.1),
                        "bar", L.FLOOR, math.pi))
    for k in range(10):                                                 # and its hall side, facing the counter
        if rng.random() < 0.7:
            out.append((L.BAR_X0 + 0.6 + k * 0.98 + rng.uniform(-0.12, 0.12), L.BAR_Y + 0.95 + rng.uniform(-0.1, 0.15),
                        "bar", L.FLOOR, math.pi + rng.uniform(-0.25, 0.25)))
    return out


def club_people(rng):
    """The same people as club_points, as (x, y, yaw, zone, floor z): what club_collide.py reads (yaw None -> facing
    the stage). Kept for the collision map; the bake uses club_points."""
    return [(x, y, yaw if yaw is not None else _face(x, y, 0, 5), zone, z) for x, y, zone, z, yaw in club_points(rng)]
