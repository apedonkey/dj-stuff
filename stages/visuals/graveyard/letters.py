"""Our own stroke letterforms (no font): A-Z, 0-9 and Roman numerals as polylines in a box 1 high, x to the right.

Used by the sting (each stroke becomes a bone), the seance board (neon strokes) and the Witching Hour clock face.
The Dino sting's D, I, N, O, S, T, A, G, E (TribeUE/Visuals/scripts/sting.py) are kept; the rest are new, drawn in the
same monoline style. Pure Python (no bpy), so it can be checked outside Blender.

  GLYPHS[ch] = (advance width, [stroke, ...]); a stroke is a list of (x, y)
  layout(text, height, track=0.22, align="center") -> [(char, [stroke in world units, ...]), ...]
"""
import math


def arc(cx, cy, rx, ry, a0, a1, n=14):
    """Points on an ellipse arc from angle a0 to a1 (degrees, counter-clockwise positive)."""
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def _p(pts):
    return [tuple(p) for p in pts]


GLYPHS = {
    "A": (0.66, [[(0, 0), (0.33, 1), (0.66, 0)], [(0.15, 0.4), (0.51, 0.4)]]),
    "B": (0.6, [[(0, 0), (0, 1)],
                [(0, 1), (0.3, 1)] + arc(0.3, 0.75, 0.22, 0.25, 90, -90)[1:] + [(0, 0.5)],
                [(0, 0.5), (0.34, 0.5)] + arc(0.34, 0.25, 0.25, 0.25, 90, -90)[1:] + [(0, 0)]]),
    "C": (0.62, [arc(0.34, 0.5, 0.34, 0.5, 45, 315, 18)]),
    "D": (0.62, [[(0, 0), (0, 1)], [(0, 1), (0.2, 1)] + arc(0.2, 0.5, 0.42, 0.5, 90, -90)[1:] + [(0, 0)]]),
    "E": (0.54, [[(0, 0), (0, 1)], [(0, 1), (0.54, 1)], [(0, 0.5), (0.42, 0.5)], [(0, 0), (0.54, 0)]]),
    "F": (0.52, [[(0, 0), (0, 1)], [(0, 1), (0.52, 1)], [(0, 0.5), (0.42, 0.5)]]),
    "G": (0.64, [arc(0.33, 0.5, 0.33, 0.5, 40, 340, 18), [(0.38, 0.42), (0.64, 0.42), (0.64, 0.16)]]),
    "H": (0.6, [[(0, 0), (0, 1)], [(0.6, 0), (0.6, 1)], [(0, 0.5), (0.6, 0.5)]]),
    "I": (0.36, [[(0.18, 0), (0.18, 1)], [(0, 1), (0.36, 1)], [(0, 0), (0.36, 0)]]),
    "J": (0.5, [[(0.5, 1), (0.5, 0.28)] + arc(0.25, 0.28, 0.25, 0.28, 0, -180)[1:]]),
    "K": (0.58, [[(0, 0), (0, 1)], [(0.56, 1), (0, 0.4)], [(0.2, 0.62), (0.58, 0)]]),
    "L": (0.5, [[(0, 1), (0, 0), (0.5, 0)]]),
    "M": (0.74, [[(0, 0), (0, 1), (0.37, 0.38), (0.74, 1), (0.74, 0)]]),
    "N": (0.62, [[(0, 0), (0, 1)], [(0, 1), (0.62, 0)], [(0.62, 0), (0.62, 1)]]),
    "O": (0.66, [arc(0.33, 0.5, 0.33, 0.5, 90, 270), arc(0.33, 0.5, 0.33, 0.5, -90, 90)]),
    "P": (0.56, [[(0, 0), (0, 1)], [(0, 1), (0.3, 1)] + arc(0.3, 0.74, 0.24, 0.26, 90, -90)[1:] + [(0, 0.48)]]),
    "Q": (0.66, [arc(0.33, 0.5, 0.33, 0.5, 90, 270), arc(0.33, 0.5, 0.33, 0.5, -90, 90),
                 [(0.4, 0.24), (0.7, -0.06)]]),
    "R": (0.58, [[(0, 0), (0, 1)], [(0, 1), (0.3, 1)] + arc(0.3, 0.74, 0.24, 0.26, 90, -90)[1:] + [(0, 0.48)],
                 [(0.22, 0.48), (0.58, 0)]]),
    "S": (0.58, [arc(0.29, 0.75, 0.29, 0.25, 15, 270, 12) + arc(0.29, 0.25, 0.29, 0.25, 90, -165, 12)[1:]]),
    "T": (0.62, [[(0, 1), (0.62, 1)], [(0.31, 1), (0.31, 0)]]),
    "U": (0.6, [[(0, 1), (0, 0.32)] + arc(0.3, 0.32, 0.3, 0.32, 180, 360)[1:] + [(0.6, 1)]]),
    "V": (0.64, [[(0, 1), (0.32, 0), (0.64, 1)]]),
    "W": (0.86, [[(0, 1), (0.2, 0), (0.43, 0.64), (0.66, 0), (0.86, 1)]]),
    "X": (0.6, [[(0, 0), (0.6, 1)], [(0, 1), (0.6, 0)]]),
    "Y": (0.62, [[(0, 1), (0.31, 0.5), (0.62, 1)], [(0.31, 0.5), (0.31, 0)]]),
    "Z": (0.56, [[(0, 1), (0.56, 1), (0, 0), (0.56, 0)]]),
    "0": (0.58, [arc(0.29, 0.5, 0.29, 0.5, 90, 450, 24)]),
    "1": (0.44, [[(0.06, 0.78), (0.26, 1), (0.26, 0)], [(0.04, 0), (0.48, 0)]]),
    "2": (0.56, [arc(0.28, 0.71, 0.28, 0.29, 160, -38, 12) + [(0, 0), (0.56, 0)]]),
    "3": (0.56, [arc(0.27, 0.76, 0.25, 0.24, 150, -90, 12) + arc(0.27, 0.26, 0.29, 0.26, 90, -150, 12)[1:]]),
    "4": (0.6, [[(0.46, 0), (0.46, 1), (0, 0.3), (0.6, 0.3)]]),
    "5": (0.56, [[(0.52, 1), (0.06, 1), (0.03, 0.56)] + arc(0.27, 0.31, 0.29, 0.31, 125, -150, 14)[1:]]),
    "6": (0.58, [[(0.46, 1), (0.08, 0.42)], arc(0.29, 0.3, 0.29, 0.3, 90, 450, 20)]),
    "7": (0.56, [[(0, 1), (0.56, 1), (0.16, 0)]]),
    "8": (0.58, [arc(0.29, 0.76, 0.24, 0.24, -90, 270, 18), arc(0.29, 0.26, 0.29, 0.26, 90, 450, 20)]),
    "9": (0.58, [arc(0.29, 0.7, 0.29, 0.3, 90, 450, 20), [(0.57, 0.62), (0.14, 0)]]),
}
for _k, (_w, _strokes) in list(GLYPHS.items()):
    GLYPHS[_k] = (_w, [_p(s) for s in _strokes])

ROMAN = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]   # clock faces use IIII
ROMAN_GLYPHS = {"I": (0.0, [[(0, 0), (0, 1)]]),
                "V": (0.56, [[(0, 1), (0.28, 0), (0.56, 1)]]),
                "X": (0.56, [[(0, 0), (0.56, 1)], [(0, 1), (0.56, 0)]])}


def layout(text, height, track=0.22, align="center", glyphs=None):
    """[(char, [stroke, ...])] of a line of text in world units (x right, y up), baseline at y = 0; a space advances
    0.45. align: 'center' puts the line's middle at x = 0, 'left' its start."""
    g = glyphs or GLYPHS
    widths = [0.45 if ch == " " else g[ch][0] for ch in text]
    total = sum(widths) + track * (len(text) - 1)
    x = -total / 2 if align == "center" else 0.0
    out = []
    for ch, w in zip(text, widths):
        if ch != " ":
            out.append((ch, [[((x + px) * height, py * height) for px, py in s] for s in g[ch][1]]))
        x += w + track
    return out


def text_width(text, track=0.22, glyphs=None):
    g = glyphs or GLYPHS
    return sum(0.45 if ch == " " else g[ch][0] for ch in text) + track * (len(text) - 1)


def roman(numeral, height, track=0.34, bars=False):
    """Strokes of a Roman numeral (centered); bars=True adds a bar above and below spanning it."""
    lines = layout(numeral, height, track=track, glyphs=ROMAN_GLYPHS)
    strokes = [s for _, ss in lines for s in ss]
    if not bars:
        return strokes
    xs = [p[0] for s in strokes for p in s]
    x0, x1 = min(xs) - 0.12 * height, max(xs) + 0.12 * height
    return strokes + [[(x0, 0.0), (x1, 0.0)], [(x0, height), (x1, height)]]
