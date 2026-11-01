"""REACTOR's drone ("selfie") camera reel: writes out_club/drone_path.club.txt in the hook's path-mode syntax
(hook/dumper.cpp drone_load_path: `fly <secs> <x,y,z> <x,y,z> [look=dj|x,y,z]`, `orbit <secs> [r=] [h=] [deg=] [start=]`;
world cm, Tribe's DJ rig at the origin, the crowd toward -Y, the stage and screen toward +Y) and checks every shot
against the room (club_layout.py): inside the walls, under the ceiling and the trusses, over the floors and the stage
deck, clear of the screen, the mezzanine decks, the rod columns, the console and the side columns. Plain Python.

    python club_drone_reel.py [out_dir]          (default: ./out_club)

The user (2026-10-09): "for the selfie camera, itll have to have a different flight path for this venue". The Dino
Stage's festival reel starts at (0, -5200, 1800): behind REACTOR's back wall (y -3050) and above its ceiling (z 980).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import club_layout as L  # noqa: E402

HEAD = (-6.0, 87.0, 168.0)          # the DJ's head at the decks (PlayerStartDJ + eye height), world cm
CLEAR = 45.0                        # cm the camera keeps from any surface

SHOTS = [
    ("overview from the back, over the bar, pushing in on the stage",
     ("fly", 12, (0, -2700, 720), (0, -1650, 620), (0, 420, 420))),
    ("low pass across the crowd's heads, the stage and screen in view",
     ("fly", 10, (-620, -950, 130), (620, -1350, 130), (0, 300, 420))),
    ("over the crowd toward you",
     ("fly", 8, (0, -1500, 240), (0, -430, 210), "dj")),
    ("close orbit around you (clear of the rod columns at x +-300)",
     ("orbit", 15, 220, 30, 360, -90)),
    ("over your shoulder: the crowd ahead",
     ("fly", 8, (-240, 380, 250), (240, 380, 250), (0, -2000, 0))),
    ("low hero angle from the stage lip, looking up past you at the core window",
     ("fly", 8, (-400, -240, 60), (400, -240, 60), (0, 300, 620))),
    ("from over the right mezzanine's front, sweeping toward the stage",
     ("fly", 10, (-700, -1050, 460), (-320, -520, 380), (0, 200, 320))),
    ("crane up from the photo pit",
     ("fly", 10, (0, -330, -50), (0, -330, 680), (0, 300, 520))),
    ("low over the front rows: you with the core window behind",
     ("fly", 10, (320, -720, 190), (-320, -720, 190), (0, 120, 380))),
]


def floor_z(x, y):
    """the walkable surface under (world cm): the stage deck at 0 from the lip on, the hall floor before it"""
    return 0.0 if y >= 100.0 * L.LIP_Y else 100.0 * L.FLOOR


def problems(p):
    """why a camera point is not clear of the room (world cm), or None"""
    X, Y, Z = p
    x, y, z = -X / 100.0, Y / 100.0, Z / 100.0                       # club frame (m)
    c = CLEAR / 100.0
    if abs(x) > L.HX - c:
        return "side wall"
    if y < L.Y_BACK + c:
        return "back wall"
    if y > L.SCREEN_Y - 0.15 - c:
        return "screen wall"
    ceil = L.CEIL if y < L.LIP_Y else L.STAGE_CEIL
    if z > ceil - c:
        return "ceiling"
    if z < floor_z(X, Y) / 100.0 + 0.3:
        return "floor / stage deck"
    for ty in L.TRUSS_Y:                                              # hall trusses x -11.4..11.4 at TRUSS_Z
        if abs(y - ty) < 0.35 + c and abs(z - L.TRUSS_Z) < 0.35 + c:
            return f"truss y {ty}"
    (fx0, fy, fz), (fx1, _fy, _fz) = L.FRONT_TRUSS
    if abs(y - fy) < 0.35 + c and abs(z - fz) < 0.35 + c:
        return "front truss"
    if abs(x) > L.MZ_X0 - c and L.MZ_Y0 - c < y < L.MZ_Y1 + c and L.MZ_Z - 0.3 - c < z < L.MZ_Z + 1.2 + c:
        return "mezzanine deck / rail"
    for sx in (-1, 1):
        if math.hypot(x - sx * L.ROD_X, y - L.ROD_Y) < 0.28 + c and z < 3.75 + c:
            return "rod column"
    T = L.TABLE
    if T["x0"] - c < x < T["x1"] + c and T["y0"] - c < y < T["y1"] + c and z < T["top"] + c:
        return "console"
    for sx in (-1, 1):                                                # wall columns (none on the airlock side at -6/-3)
        for cy in L.COL_Y:
            if sx < 0 and cy > L.AIR_Y0 - 1.0:
                continue
            if abs(x) > L.HX - 0.6 - c and abs(y - cy) < 0.3 + c:
                return "wall column"
    if L.AIR_X0 - c < x < L.AIR_X1 + c and L.AIR_Y0 - c < y < L.AIR_Y1 and z < L.LINTEL_TOP + 0.1 + c:
        return "airlock"
    return None


def samples(shot):
    kind = shot[0]
    if kind == "fly":
        _k, _secs, a, b, _look = shot
        n = max(2, int(math.dist(a, b) / 10.0))
        return [tuple(a[i] + (b[i] - a[i]) * k / n for i in range(3)) for k in range(n + 1)]
    _k, _secs, r, h, deg, start = shot
    n = max(8, int(abs(deg) / 2))
    return [(HEAD[0] + r * math.cos(math.radians(start + deg * k / n)), HEAD[1] + r * math.sin(math.radians(start + deg * k / n)),
             HEAD[2] + h) for k in range(n + 1)]


def line(shot):
    kind = shot[0]
    if kind == "fly":
        _k, secs, a, b, look = shot
        lk = "dj" if look == "dj" else ",".join(f"{v:g}" for v in look)
        return f"fly {secs:g} {','.join(f'{v:g}' for v in a)} {','.join(f'{v:g}' for v in b)} look={lk}"
    _k, secs, r, h, deg, start = shot
    return f"orbit {secs:g} r={r:g} h={h:g} deg={deg:g} start={start:g}"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out_club")
    os.makedirs(out, exist_ok=True)
    ok, total = True, 0.0
    for desc, shot in SHOTS:
        bad = [(p, why) for p in samples(shot) if (why := problems(p))]
        total += shot[1]
        print(f"  [{'PASS' if not bad else 'FAIL'}] {line(shot)}  # {desc}"
              + (f"\n         first clash at ({bad[0][0][0]:.0f}, {bad[0][0][1]:.0f}, {bad[0][0][2]:.0f}): {bad[0][1]}" if bad else ""))
        ok &= not bad
    path = os.path.join(out, "drone_path.club.txt")
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write("# REACTOR drone reel (Scripts/Blender/club/club_drone_reel.py; every shot checked against the room).\n"
                "# World cm: the DJ rig at the origin, the crowd toward -Y, the stage and core window toward +Y.\n")
        for desc, shot in SHOTS:
            f.write(f"# {desc}\n{line(shot)}\n")
    print(f"{len(SHOTS)} shots, {total:.0f} s loop -> {path}")
    print("ALL SHOTS CLEAR" if ok else "SOME SHOTS CLASH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
