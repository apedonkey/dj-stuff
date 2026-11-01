"""annotate the concept renders with the projected labels: python -P annotate.py <dir> view1 view2 ...
(system python + PIL; reads bigdub_concept_<view>.png + labels_<view>.json, writes bigdub_concept_<view>.jpg)"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

d, views = sys.argv[1], sys.argv[2:]
FONT = "C:/Windows/Fonts/arialbd.ttf"
SIZE = {"stage": 32, "place": 24, "camp": 22}
COLOR = {"stage": (255, 230, 60), "place": (255, 255, 255), "camp": (170, 255, 170)}
TOP_VIEWS = {"aerial", "aerial_top", "core_top", "aerial_main", "main_side"}
MAXDIST = {"aerial": 1e9, "aerial_top": 1e9, "core_top": 1e9, "aerial_main": 600, "main_side": 300}
ORDER = {"stage": 0, "place": 1, "camp": 2}


def overlaps(box, boxes):
    x0, y0, x1, y1 = box
    return any(x0 < bx1 and x1 > bx0 and y0 < by1 and y1 > by0 for bx0, by0, bx1, by1 in boxes)


for v in views:
    png = f"{d}/bigdub_concept_{v}.png"
    if not os.path.exists(png): print("missing", v); continue
    im = Image.open(png).convert("RGB"); W, H = im.size; dr = ImageDraw.Draw(im)
    labels = json.load(open(f"{d}/labels_{v}.json"))
    maxdist = MAXDIST.get(v, 220)
    boxes = []
    for L in sorted(labels, key=lambda L: (ORDER[L["kind"]], L["dist"])):
        if L["depth"] <= 0 or not (0 <= L["px"] <= W and 0 <= L["py"] <= H): continue
        if L["kind"] == "stage" and v not in TOP_VIEWS and L["dist"] > 400: continue
        if L["kind"] != "stage" and L["dist"] > maxdist: continue
        if v not in TOP_VIEWS and L["kind"] == "camp": continue
        font = ImageFont.truetype(FONT, SIZE[L["kind"]])
        tw, th = dr.textbbox((0, 0), L["text"], font=font)[2:]
        x, y = L["px"], L["py"]
        # candidate anchors around the point: above, right, left, below, then diagonals, then further out
        cands = []
        for k in (1, 2, 3):
            g = 12 * k
            cands += [(x - tw / 2, y - th - g), (x + g, y - th / 2), (x - tw - g, y - th / 2), (x - tw / 2, y + g),
                      (x + g, y - th - g), (x - tw - g, y - th - g), (x + g, y + g), (x - tw - g, y + g)]
        placed = None
        for tx, ty in cands:
            tx, ty = min(max(tx, 4), W - tw - 4), min(max(ty, 4), H - th - 30)
            box = (tx - 4, ty - 2, tx + tw + 4, ty + th + 2)
            if not overlaps(box, boxes): placed = (tx, ty, box); break
        if placed is None: continue                      # crowded spot: drop the least important label rather than cascade
        tx, ty, box = placed; boxes.append(box)
        r = 7 if L["kind"] == "stage" else 4
        dr.ellipse((x - r, y - r, x + r, y + r), fill=COLOR[L["kind"]], outline=(0, 0, 0), width=2)
        ax, ay = min(max(x, tx), tx + tw), min(max(y, ty), ty + th)
        if abs(ax - x) + abs(ay - y) > 10: dr.line((x, y, ax, ay), fill=COLOR[L["kind"]], width=2)
        dr.text((tx, ty), L["text"], font=font, fill=COLOR[L["kind"]], stroke_width=3, stroke_fill=(0, 0, 0))
    dr.text((12, H - 34), f"Big Dub blockout - {v} - boxes only, layout per plan v3 (not final art)", font=ImageFont.truetype(FONT, 20), fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    im.save(f"{d}/bigdub_concept_{v}.jpg", quality=90); print("annotated", v, len(boxes), "labels")
