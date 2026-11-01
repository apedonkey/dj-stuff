"""bd_compare.py: BIG DUB's before/after sheet (python -P; PIL). Pairs each picture in build/renders/bigdub_before/ with
the picture of the same name in build/renders/ (the same camera, Scripts/render/bigdub_views.py), before on the left and
after on the right, half size, labelled, into build/renders/bigdub_compare.png.

    python -P D:/VRDJ/tools/bigdub/bd_compare.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RENDERS = os.path.join(ROOT, "build", "renders")
BEFORE = os.path.join(RENDERS, "bigdub_before")
PAIRS = [("bigdub_mainstage.png", "MAIN STAGE, the DJ's eye"), ("bigdub_spot2.png", "PAVILION, the DJ's eye"),
         ("bigdub_spot3.png", "NEW CAMP, the DJ's eye"), ("bigdub_ring.png", "the Stone Circle from its far end, 6 m up"),
         ("bigdub_forest.png", "the Big Bottom's path")]
W, H, LABEL, GAP = 960, 540, 34, 8


def main():
    sheet = Image.new("RGB", (2 * W + GAP, len(PAIRS) * (H + LABEL)), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    for row, (name, what) in enumerate(PAIRS):
        y = row * (H + LABEL)
        for col, folder, tag in ((0, BEFORE, "BEFORE"), (1, RENDERS, "AFTER")):
            im = Image.open(os.path.join(folder, name)).convert("RGB").resize((W, H), Image.LANCZOS)
            x = col * (W + GAP)
            sheet.paste(im, (x, y + LABEL))
            d.text((x + 10, y + 10), f"{tag}: {what} ({name})", fill=(235, 235, 235))
    out = os.path.join(RENDERS, "bigdub_compare.png")
    sheet.save(out)
    print(f"{out}: {sheet.size[0]} x {sheet.size[1]}, {len(PAIRS)} pairs")


if __name__ == "__main__":
    main()
