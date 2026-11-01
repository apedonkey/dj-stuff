"""The Dino's laser program on the club's laser rigs (v6, 2026-10-09). Pure numpy: club_stage.py writes the club's
T_ClubLaserProg / T_ClubLaserLib through it, and it runs on its own to refresh them without a bake:
    python club_laser_scenes.py OUT_DIR          (system Python; imports the Dino's show.py, read only)

dino_materials.laser_show gates every beam by a group mask: the pattern's own mask (lib texel 5, z) if it has one, else
the bar's scene (prog alpha, show.py v12). Its families: fan 1, horns 2, towers 4, lip 8, mouth 16, delay 32 (bits). The
club's laser groups are the front-truss fans (group 0 -> the fan family) and the mezzanine poles + back truss (groups 1
and 2 -> the horns family). The Dino's scenes as they are left the club with no lasers in 9-13 of every 32 bars (the
towers + delay and lip-only scenes: bars 4-10 in every variant). Here a mask keeps its fan / horns bits; a mask with
neither lights the club rig that stands in for the Dino's groups: lip / mouth (the head's front) -> the front fans,
towers / delay (around the field) -> the poles and the back truss. 0 (= every group) stays 0."""
import os
import sys

import numpy as np

FAN, HORNS, TOWERS, LIP, MOUTH, DELAY = 1, 2, 4, 8, 16, 32
CLUB_FAMILIES = (0, 1)                     # laser_show's fam for the club's groups 0, 1, 2: 0, 1, 1


def club_mask(m):
    """A Dino group mask -> the club's (see the module docstring)."""
    m = int(m)
    if m == 0:
        return 0
    c = m & (FAN | HORNS)
    if not c:
        c = (FAN if m & (LIP | MOUTH) else 0) | (HORNS if m & (TOWERS | DELAY) else 0)
    return c or (FAN | HORNS)


def _remap(channel):
    """A float texture channel holding masks as bytes, remapped in place."""
    b = np.floor(channel * 255.0 + 0.5).astype(int)
    for idx in zip(*np.nonzero(b)):
        channel[idx] = club_mask(b[idx]) / 255.0


def club_textures(show):
    """(prog, lib) for the club: show.tex_laser_prog() / tex_laser_lib() with every mask on the club's rigs."""
    prog, lib = show.tex_laser_prog(), show.tex_laser_lib()
    _remap(prog[..., 3])                                   # the bars' scenes
    _remap(lib[:len(show.PATTERNS), 5, 2])                 # the patterns' own masks (texel 5, z)
    return prog, lib


def dark_bars(prog, lib):
    """[(variant, bar)] where a lit bar leaves every club family off (the shader's gmask / gbit, before TopLasers and
    the drop boom, which light everything anyway)."""
    out = []
    for v in range(prog.shape[0]):
        for bar in range(prog.shape[1]):
            r, _, level, a = prog[v, bar]
            if level <= 0:
                continue
            row = int(np.floor(r * 255.0 + 0.5))
            gm = int(np.floor(lib[row, 5, 2] * 255.0 + 0.5)) or int(np.floor(a * 255.0 + 0.5))
            if gm and not any((gm >> fam) & 1 for fam in CLUB_FAMILIES):
                out.append((v, bar))
    return out


def main():
    out = sys.argv[1]
    sys.path.insert(1, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import show
    raw = (show.tex_laser_prog(), show.tex_laser_lib())
    prog, lib = club_textures(show)
    print(f"the Dino's scenes as they are: {len(dark_bars(*raw))} dark (variant, bar) for the club; "
          f"remapped: {len(dark_bars(prog, lib))}")
    assert not dark_bars(prog, lib)
    show.write_png_linear(os.path.join(out, "T_ClubLaserProg.png"), prog)
    show.write_png_linear(os.path.join(out, "T_ClubLaserLib.png"), lib)


if __name__ == "__main__":
    main()
