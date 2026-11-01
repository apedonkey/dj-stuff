"""GRAVEYARD SHIFT v7 deck dressing and the way down to the crowd: one list that hw_stage.py builds (geometry, pool
lights) and intro/hw_collide.py walls off (walking map), so the two never disagree. Plain Python, no Blender.

The user, 2026-10-11, after visiting v6: "a little too bright on stage, something is missing... it seems empty"; then
chose A (deck and riser near-black, light only in pools) + B (fill the empty wings: speaker stacks dressed as coffins,
subs, tombstones, dead trees, candelabras, pumpkin piles) + a low C (ground fog). And "is there a pathway into the
crowd?": free roam, the whole crowd field walkable (the user walks through the dancers).

Frame: hw_stage.py's final Blender frame (m): the deck top at DECK_Z = -1.0, the field at FIELD_Z = -2.5, crowd -Y.
The walkable deck is x -25..25, y -4.5..7.8 (the gate line); the riser x -4.5..4.5, y -2.5..3.0 with its back-corner
stairs out to |x| 5.9; deck-front laser posts at x +-3, 9, 15 and flame bases at +-6, 12, 18 (y -4.5..-3.75); skull
piles at x +-6, y -3.3. Every prop stays clear of those, under 3.3 m (the lasers' 3 m rule over the deck is solved
against the props anyway), and outside the screen's width (|x| <= 11.5) when it is taller than 1.2 m.
"""
DECK_Z, FIELD_Z = -1.0, -2.5

# kind, x, y, size: coffin_stack (w, d, h) | sub_stack (w, d, h) | tomb (w, d, h, tilt deg) | tree (h) |
# candelabra (h) | pumpkins (n, radius of the pile)
_HALF = [
    ("coffin_stack", 17.5, 6.0, (2.2, 1.0, 3.2)),
    ("sub_stack", 21.6, -3.0, (2.2, 0.9, 1.1)),
    ("tree", 22.6, 6.2, (3.2,)),
    ("tomb", 8.6, 1.4, (0.55, 0.16, 0.85, -6.0)),
    ("tomb", 10.2, 4.6, (0.7, 0.18, 1.05, 4.0)),
    ("tomb", 12.6, 0.6, (0.5, 0.15, 0.7, 9.0)),
    ("tomb", 14.2, 3.4, (0.6, 0.16, 0.95, -3.0)),
    ("tomb", 20.0, 1.2, (0.55, 0.16, 0.8, 7.0)),
    ("tomb", 23.2, 3.0, (0.65, 0.18, 1.0, -8.0)),
    ("tomb", 19.4, -1.4, (0.5, 0.15, 0.65, 12.0)),
    ("tomb", 9.2, -1.4, (0.45, 0.14, 0.6, -10.0)),
    ("candelabra", 11.0, -2.0, (1.9,)),
    ("candelabra", 15.8, 1.6, (1.9,)),
    ("candelabra", 21.0, 4.6, (1.7,)),
    ("pumpkins", 13.6, -2.4, (5, 0.6)),
    ("pumpkins", 17.4, 3.4, (4, 0.5)),
    ("pumpkins", 24.0, 0.4, (3, 0.4)),
]
PROPS = [(k, sx * x, y, size, sx) for sx in (-1, 1) for k, x, y, size in _HALF]

# the way down (free roam): centre stairs off the deck front between the two middle laser posts, through a gap in
# the iron barrier (y -7.5) into the crowd field
STAIR_HALF_W = 1.4
STAIR_N, STAIR_D = 8, 0.34                    # 8 steps of 0.1875 m (the walking rules allow 0.45), 0.34 m deep
STAIR_Y0 = -4.5                               # the deck's front edge; the stairs end at y -4.5 - 8 x 0.34 = -7.22
BARRIER_Y, BARRIER_GAP = -7.5, 1.9            # the barrier's posts and rails stop at |x| < 1.9 (a gateway)


def stair_steps():
    """[(y_top_edge, y_bottom_edge, top z)] from the deck down: step k's top is the deck minus (k + 1) risers."""
    rise = (DECK_Z - FIELD_Z) / STAIR_N
    return [(STAIR_Y0 - k * STAIR_D, STAIR_Y0 - (k + 1) * STAIR_D, DECK_Z - (k + 1) * rise) for k in range(STAIR_N - 1)]


def footprint(kind, x, y, size):
    """(x0, y0, x1, y1, height over the deck) of a prop: its walking-map wall."""
    if kind in ("coffin_stack", "sub_stack"):
        w, d, h = size
        return x - w / 2, y - d / 2, x + w / 2, y + d / 2, h
    if kind == "tomb":
        w, d, h, _ = size
        return x - w / 2 - 0.05, y - d / 2 - 0.05, x + w / 2 + 0.05, y + d / 2 + 0.05, h
    if kind == "tree":
        return x - 0.35, y - 0.35, x + 0.35, y + 0.35, size[0]
    if kind == "candelabra":
        return x - 0.3, y - 0.3, x + 0.3, y + 0.3, size[0]
    if kind == "pumpkins":
        r = size[1] + 0.25
        return x - r, y - r, x + r, y + r, 0.6
    raise ValueError(kind)
