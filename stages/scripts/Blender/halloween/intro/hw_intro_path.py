"""GRAVEYARD SHIFT intro: the Headless Horseman's ride, shared by the woods module, the preview video and the mod.

Plain Python (no bpy). The user, 2026-10-10: the stream camera follows the rider through the woods behind the stage
(low, front left, looking up) until press 1 on the backstage button; then he rides out of the trees to the back of the
stage; press 2 starts the intro song on the cued deck, rolls the door under the screen up and cuts to a wide shot from
the front of the stage; the user walks out through the door to the decks. As built (the mod's file): THREE presses on the
button in the backstage crypt: 1 starts the pre-show (the door shuts, the ride loop, the stream camera on the rider),
2 rides in (the exit at the loop's end), 3 = showtime (the cued deck plays, the wide shot, the door rises).
v5 (2026-10-10): the user swapped the roll-up door for two crypt doors ("make them 2 doors not a garage door. Like
crypt doors"); they swing out to the deck on the same DoorOpen (door_xy below is the rule). The mod's file keeps its
words ("the door rises") so its bytes, which the Dino session checked, stay the same.

Frame here: hw_stage.py's FINAL Blender frame, metres (the DJ at the origin facing -Y, the cathedral behind at +Y, the
field at z -2.5). Tribe world cm = (-x, y, z) * 100. write_mod_file() writes the mod's file in world cm.

    python hw_intro_path.py [out.txt]      (prints the timing, writes the mod file: on the headset it is
                                            tribemod/intro.halloween.txt, one intro file per stage folder)
"""
import math
import sys

FIELD_Z = -2.5
SPEED = 6.0                     # m/s: v6's gallop, 2.4 strides/s of 2.5 m (hw_rider.GALLOP_HZ)
# the loop through the woods, anticlockwise from above (the rider turns left, so the camera on his left rides the
# clear inside of the loop); it closes on its first point, where the exit branches off toward the cathedral
LOOP_PTS = [(-16.0, 88.0), (0.0, 84.0), (16.0, 86.5), (27.0, 96.0), (31.0, 110.0), (24.0, 124.0), (10.0, 131.0),
            (-6.0, 132.0), (-21.0, 126.0), (-30.0, 113.0), (-28.5, 99.0)]
# out of the trees to the back of the stage (the ruined nave: x +-15, y 15..45, CONTRACT.md) and through a gothic
# archway in its back wall (hw_stage, x -7.5) into the dark nave; the camera stops following at CAM_HOLD_S and holds on
# the moonlit back of the cathedral while he vanishes inside (a horse that stopped would gallop in place: the VAT loops)
EXIT_R = 9.0                    # the exit leaves the loop along its heading and curves right on this radius until it
EXIT_ON = [(-10.5, 70.0), (-8.6, 60.0), (-7.6, 52.0), (-7.5, 45.0), (-7.5, 38.0), (-7.5, 32.0)]   # heads south (the
# Dino session's check, 2026-10-10: the first exit turned 76 degrees in one step off the loop: a snap)


def _exit_pts():
    """The seam's heading (the closed Catmull-Rom's tangent there: half the chord between its neighbours), a tangent
    arc of radius EXIT_R turning right until it heads -Y, then EXIT_ON."""
    s0, prev, nxt = LOOP_PTS[0], LOOP_PTS[-1], LOOP_PTS[1]
    hx, hy = nxt[0] - prev[0], nxt[1] - prev[1]
    d = math.hypot(hx, hy)
    hx, hy = hx / d, hy / d
    cx, cy = s0[0] + EXIT_R * hy, s0[1] - EXIT_R * hx            # the centre: to the right of the heading
    a0 = math.atan2(s0[1] - cy, s0[0] - cx)                      # clockwise from here down to angle 0 (heading -Y)
    n = max(2, int(EXIT_R * a0 / 1.2))
    arc = [(cx + EXIT_R * math.cos(a0 * (1 - k / n)), cy + EXIT_R * math.sin(a0 * (1 - k / n))) for k in range(n + 1)]
    return arc + EXIT_ON


EXIT_PTS = None                 # filled below (it needs LOOP_PTS and the helpers)
EXIT_STOP_S = 2.0               # the last stretch eases to a stop over this long (out of sight)
CAM_HOLD_S = 4.5                # seconds into the exit when the camera stops following: it frames the moonlit back
                                # of the cathedral; he gallops on through the archway at x -7.5 into the dark nave
TREE_CLEAR_IN, TREE_CLEAR_OUT = 5.5, 3.0   # metres from the trail's centre line kept free of trunks (inside, the
                                           # camera's side / outside); branches keep out below 7 m only
# the stream camera, in the rider's frame (metres: forward along his path, left = his left, the pumpkin side; up from
# the ground); the loop's low front-left angle, and the exit's swing round behind him so the cathedral rises ahead
CAM_LOOP = ((5.0, 1.2, 0.5), (0.0, 0.0, 2.0))     # v2: more in front of him (the user could not see the
                                                  # lantern): the pumpkin and the lantern frame the horse's head
CAM_EXIT = ((-5.5, 3.2, 2.2), (10.0, 0.0, 6.5))   # behind him, framing the towers against the sky; v6: tilted
                                                  # down (look 9 -> 6.5 m) so the held shot shows the glowing
                                                  # doorway he rides into, ground and all
# press 2: the wide shot from the front of the stage, the door under the screen, the DJ booth, the first crowd rows
WIDE = ((0.0, -15.5, 4.5), (0.0, 6.5, 1.6))
# the crypt gate under the screen (hw_stage.build_gate / add_backstage; hw_materials.door_swing turns its doors)
GATE_Y, GATE_X, GATE_TOP = 7.8, 1.8, 1.9     # front face; the opening x +-1.8, the deck (-1) to 1.9
# v5: two crypt doors, each on its jamb's vertical hinge at (side x GATE_X, GATE_Y), swinging OUT to the deck: never
# into the crypt, where the user waits and the button stands
DOOR_T = 0.10                  # a leaf's thickness behind GATE_Y (its iron straps stand 1-2 cm proud of the front)
DOOR_OPEN_DEG = 110.0          # DoorOpen 1: a little past square, flung back towards the pillars
DOOR_STAGGER = 0.15            # the right leaf (+x) starts this share of the travel after the left one
BUTTON = (1.5, 9.4, 0.05)       # the backstage button (a hand within 14 cm presses it): waist height on the deck (-1)
BACKSTAGE = (-0.6, 9.2, -1.0, -90.0)   # where the user waits: in the crypt, facing the door; the player's
                                       # UE yaw (-90 faces world -Y, the crowd), as halloween_collide.txt


def door_turn_deg(side, door_open):
    """A leaf's turn about its hinge (Blender degrees, + = anticlockwise seen from above) at DoorOpen 0..1. side -1 =
    the left leaf (x < 0), +1 = the right one; the left leads, the right trails by DOOR_STAGGER of the travel."""
    delay = DOOR_STAGGER if side > 0 else 0.0
    p = min(1.0, max(0.0, (door_open - delay) / (1.0 - DOOR_STAGGER)))
    return side * DOOR_OPEN_DEG * p


def door_xy(side, x, y, door_open):
    """Where a leaf's point (x, y) (closed pose, Blender m) is at DoorOpen door_open: hw_materials.door_swing's rule
    (and the preview's, the walking map's, the laser and drone checks')."""
    a = math.radians(door_turn_deg(side, door_open))
    hx, hy = side * GATE_X, GATE_Y
    dx, dy = x - hx, y - hy
    return hx + dx * math.cos(a) - dy * math.sin(a), hy + dx * math.sin(a) + dy * math.cos(a)


def _catmull(p0, p1, p2, p3, t, alpha=0.5):
    """Centripetal Catmull-Rom (Barry-Goldman), p1 -> p2 at t 0..1: no cusps or loops where points are spaced unevenly
    (the exit's tight arc then its long straights; the uniform form backtracked there)."""
    def nxt(ti, a, b):
        return ti + max(math.dist(a, b), 1e-4) ** alpha

    def lerp(a, b, ta, tb, u):
        w = (u - ta) / (tb - ta)
        return tuple(x + (y - x) * w for x, y in zip(a, b))
    t0 = 0.0
    t1 = nxt(t0, p0, p1)
    t2 = nxt(t1, p1, p2)
    t3 = nxt(t2, p2, p3)
    u = t1 + (t2 - t1) * t
    a1, a2, a3 = lerp(p0, p1, t0, t1, u), lerp(p1, p2, t1, t2, u), lerp(p2, p3, t2, t3, u)
    b1, b2 = lerp(a1, a2, t0, t2, u), lerp(a2, a3, t1, t3, u)
    return lerp(b1, b2, t1, t2, u)


def _sample(pts, closed, step=0.25):
    """Dense points along a Catmull-Rom curve through pts (closed: wraps), about `step` metres apart."""
    n = len(pts)
    segs = n if closed else n - 1
    out = []
    for i in range(segs):
        p1, p2 = pts[i % n], pts[(i + 1) % n]
        if closed:
            p0, p3 = pts[(i - 1) % n], pts[(i + 2) % n]
        else:                                                    # open ends: mirror the neighbour (no zero chords)
            p0 = pts[i - 1] if i > 0 else tuple(2 * a - b for a, b in zip(p1, p2))
            p3 = pts[i + 2] if i + 2 < n else tuple(2 * b - a for a, b in zip(p1, p2))
        chord = math.dist(p1, p2)
        k = max(2, int(chord / step))
        out += [_catmull(p0, p1, p2, p3, j / k) for j in range(k)]
    out.append(pts[0] if closed else pts[-1])
    return out


def _arclength(pts):
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + math.dist(a, b))
    return s


def path():
    """(loop samples, exit samples) as lists of (x, y) with their arc lengths."""
    global EXIT_PTS
    if EXIT_PTS is None:
        EXIT_PTS = _exit_pts()
    loop = _sample(LOOP_PTS, True)
    ex = _sample(EXIT_PTS, False)
    return (loop, _arclength(loop)), (ex, _arclength(ex))


def timing():
    (loop, ls), (ex, es) = path()
    t_loop = ls[-1] / SPEED
    t_exit = es[-1] / SPEED + EXIT_STOP_S / 2.0          # the eased stop adds half its length
    return t_loop, t_exit, ls[-1], es[-1]


def pose_at(samples, arcs, s):
    """(x, y, heading (dx, dy)) at arc length s along a sampled curve."""
    s = max(0.0, min(arcs[-1], s))
    i = max(0, min(len(arcs) - 2, next((k for k in range(1, len(arcs)) if arcs[k] >= s), len(arcs) - 1) - 1))
    a, b = samples[i], samples[i + 1]
    f = 0.0 if arcs[i + 1] == arcs[i] else (s - arcs[i]) / (arcs[i + 1] - arcs[i])
    x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
    d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    return x, y, ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def exit_s(t):
    """Arc length along the exit at time t (seconds since it began): full speed, then an eased stop at the end."""
    _, (ex, es) = path()
    L = es[-1]
    t_full = (L - SPEED * EXIT_STOP_S / 2.0) / SPEED
    if t <= t_full:
        return SPEED * t
    u = min(1.0, (t - t_full) / EXIT_STOP_S)
    return SPEED * t_full + SPEED * EXIT_STOP_S * (u - u * u / 2.0)


def yaw_deg(dx, dy):
    """The rider actor's world yaw for travel along the Blender direction (dx, dy): its mesh faces Blender -Y, so
    yaw 180 = facing world -Y like the level (Blender (x, y, z) -> world (-x, y, z) * 100). = atan2(dx, dy)."""
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _cm(v):
    """Metres -> integer cm text without a negative zero."""
    c = round(v * 100)
    return str(c if c != 0 else 0)


FOV_RIDE, FOV_WIDE = 79, 66     # the stream camera's horizontal FOV (deg) in the woods / the wide shot: the preview's
                                # 22 / 28 mm lenses on a 36 mm film back; the mod sets them and restores Tribe's
HOLD_S, BACK_S = 2.0, 20.0      # showtime: seconds of dark before the deck plays; the camera's hand-back timeout


def write_mod_file(out, key_step=0.25):
    """The mod's intro file (the Dino session's proposed format, world cm): keys every key_step seconds."""
    (loop, ls), (ex, es) = path()
    t_loop, t_exit, L_loop, L_exit = timing()
    lines = ["# GRAVEYARD SHIFT intro ride (hw_intro_path.py). World cm, Catmull-Rom between keys, yaw = the rider",
             "# actor's world yaw (its mesh faces local +Y after the import; yaw 180 faces world -Y like the level).",
             f"# loop {L_loop:.0f} m in {t_loop:.1f} s, exit {L_exit:.0f} m in {t_exit:.1f} s; speed {SPEED} m/s.",
             "# cam / look offsets: forward along the path, LEFT = the rider's left (the pumpkin side), up from the",
             "# ground under him; in UE world, left = (f.y, -f.x) for the forward f (left-handed axes)."]

    def key(t, x, y, d):
        lines.append(f"key {t:.3f} {_cm(-x)},{_cm(y)},{_cm(FIELD_Z)} {yaw_deg(*d):.1f}")
    n = max(2, int(round(t_loop / key_step)))
    for i in range(n + 1):
        t = t_loop * i / n
        x, y, d = pose_at(loop, ls, SPEED * t if i < n else 0.0)
        key(t, x, y, d)
    m = max(2, int(round(t_exit / key_step)))
    for i in range(1, m + 1):
        t = t_exit * i / m
        x, y, d = pose_at(ex, es, exit_s(t))
        key(t_loop + t, x, y, d)
    lines.append(f"loop 0.000 {t_loop:.3f}")
    lines.append(f"exit {t_loop:.3f} {t_loop + t_exit:.3f}")
    lines.append(f"camhold {t_loop + CAM_HOLD_S:.3f}")
    lines.append("# after camhold the camera keeps its last pose; at the exit's end the rider is out of sight: hide him")
    for name, (c, lk) in (("loop", CAM_LOOP), ("exit", CAM_EXIT)):
        lines.append(f"cam {name} {_cm(c[0])},{_cm(c[1])},{_cm(c[2])} look={_cm(lk[0])},{_cm(lk[1])},{_cm(lk[2])}")
    (wx, wy, wz), (lx, ly, lz) = WIDE
    lines.append(f"wide {_cm(-wx)},{_cm(wy)},{_cm(wz)} look={_cm(-lx)},{_cm(ly)},{_cm(lz)}")
    bx, by, bz = BUTTON
    lines.append(f"button {_cm(-bx)},{_cm(by)},{_cm(bz)} r=14")
    sx, sy, sz, syaw = BACKSTAGE
    lines.append(f"spot backstage {_cm(-sx)},{_cm(sy)},{_cm(sz)} {syaw:.0f}")
    lines += ["# the actors and scalars (build_halloween.py): the rider is parked 50 m below until the intro moves him;",
              "# the woods are only ever seen by the intro's camera: show them for the intro, hide them after showtime",
              "rider HwRider",
              "woods HwWoods HwWoodsGlow",
              "# MPC_HwShow: IntroStep 0 idle, 1 the pre-show ride, 2 riding in, 3 showtime (the button's colour follows);",
              "# DoorOpen 0 shut .. 1 open, 1 when no intro runs: shut it (eased over 'door' s) at step 1, open it at 3",
              "step IntroStep",
              "door DoorOpen 4.0",
              "# presses: 1 starts the pre-show (the door shuts behind the user, the ride loop, the stream camera on the",
              "# rider), 2 takes the exit at the loop's end, 3 = showtime (the cued deck plays, the wide shot, the door rises)",
              "presses 3",
              f"fov ride {FOV_RIDE}",
              f"fov wide {FOV_WIDE}",
              f"hold {HOLD_S:.1f}",
              f"back {BACK_S:.0f}"]
    open(out, "w").write("\n".join(lines) + "\n")
    return lines


if __name__ == "__main__":
    t_loop, t_exit, L_loop, L_exit = timing()
    print(f"loop {L_loop:.1f} m = {t_loop:.1f} s at {SPEED} m/s; exit {L_exit:.1f} m = {t_exit:.1f} s; "
          f"press 1 -> arrival: {t_exit:.1f} s .. {t_loop + t_exit:.1f} s (mean {t_loop / 2 + t_exit:.1f} s)")
    if len(sys.argv) > 1:
        write_mod_file(sys.argv[1])
        (loop, ls), (ex, es) = path()
        h_loop = math.degrees(math.atan2(loop[1][0] - loop[-2][0], loop[1][1] - loop[-2][1]))
        h_exit = math.degrees(math.atan2(ex[1][0] - ex[0][0], ex[1][1] - ex[0][1]))
        turn = max(abs(math.degrees(math.atan2(math.sin(a2 - a1), math.cos(a2 - a1))))
                   for a1, a2 in zip([math.atan2(b[0] - a[0], b[1] - a[1]) for a, b in zip(ex, ex[1:])],
                                     [math.atan2(b[0] - a[0], b[1] - a[1]) for a, b in zip(ex[1:], ex[2:])]))
        print(f"seam: loop heading {h_loop:.1f}, exit {h_exit:.1f} deg; sharpest exit step {turn:.1f} deg; "
              f"{sum(1 for l in open(sys.argv[1]) if l.startswith('key'))} keys")
