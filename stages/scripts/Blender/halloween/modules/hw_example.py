"""A minimal example module (the contract in CONTRACT.md): one lantern post with a lit lantern, its light, a keep-out
rect, one extra person and a coffin with a hinged lid. Not loaded by hw_stage.py (it loads the modules listed in its HW_MODULES)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *  # noqa: E402,F401,F403

NAME = "example"
BAKE_SIZE = 1024


def build(rng):
    lit, glow = bmesh.new(), bmesh.new()
    x, y = -32.0, -20.0
    cyl(lit, (x, y, GROUND_Z), (x, y, GROUND_Z + 3.0), 0.08, segs=6)              # the post (metal_dark)
    box(lit, (x, y, GROUND_Z + 3.05), (0.5, 0.5, 0.1))
    glow_faces(glow, box(glow, (x, y, GROUND_Z + 2.7), (0.3, 0.3, 0.4)), "fire")  # the lantern (unlit, palette)
    coffin, lid = bmesh.new(), bmesh.new()                                         # a coffin whose lid swings open
    cx = x + 3.0
    box(coffin, (cx, y, GROUND_Z + 0.25), (0.8, 2.0, 0.5))
    box(lid, (cx, y, GROUND_Z + 0.53), (0.8, 2.0, 0.06))
    return {
        "lit": [(lit, "metal_dark"), (coffin, "wood_dark")],
        # hinged: the lid turns 100 degrees about the +Y line along its +x edge (a right-hand turn lifts its -x edge)
        "hinged": [(lid, "wood_dark", (cx + 0.4, y, GROUND_Z + 0.5), (0.0, 1.0, 0.0), 100.0, 0.2)],
        "glow": [glow],
        "lights": [light("ExLantern", "POINT", (x, y, GROUND_Z + 2.7), GLOW["fire"], 250, size=0.2)],
        "exclude": [(x - 1, y - 1, x + 1, y + 1)],
        "people": [(x + 1.5, y, 1.57, "hips")],
    }
