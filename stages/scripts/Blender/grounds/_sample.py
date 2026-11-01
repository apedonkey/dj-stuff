"""Smoke test of the kit + preview harness (not shipped)."""
from kit import *

NAME = "sample"
BAKE_SIZE = 1024


def build(rng):
    lit_canvas, lit_metal, glow = bmesh.new(), bmesh.new(), bmesh.new()
    beams, halos = bmesh.new(), bmesh.new()
    x, y, z = -40.0, -25.0, GROUND_Z
    box(lit_canvas, (x, y, z + 1.4), (4, 4, 2.8))
    cone(lit_canvas, (x, y, z + 2.8), (x, y, z + 4.2), 3.0, segs=4)
    cyl(lit_metal, (x + 3, y - 3, z), (x + 3, y - 3, z + 5), 0.08)
    cyl(lit_metal, (x + 3, y + 3, z), (x + 3, y + 3, z + 5), 0.08)
    string_lights(lit_metal, glow, (x + 3, y - 3, z + 4.9), (x + 3, y + 3, z + 4.9), 0.6)
    led_text(glow, "TACOS", (x + 2.05, y + 1.6, z + 2.0), (0, -1, 0), (0, 0, 1), pixel=0.1, key="amber")
    beam_planes(beams, (x, y, z + 6), (0.2, 0.1, 1), 60, 0.3, 6, color="cyan")
    halo(halos, (x + 3, y, z + 4.5), 2.0, color="amber")
    return {"lit": [(lit_canvas, "canvas_white"), (lit_metal, "metal_dark")], "glow": [glow], "beams": [beams],
            "halos": [halos],
            "lights": [light("TacoLamp", "POINT", (x + 2.6, y, z + 2.6), (1.0, 0.7, 0.4), 400, size=0.2)],
            "exclude": [(x - 3, y - 3, x + 3, y + 3)], "people": [(x + 3.5, y, -1.57, "down")]}
