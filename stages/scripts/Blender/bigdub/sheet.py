"""contact sheet of the concept renders: python sheet.py <dir> <out.jpg> view1 view2 ... (system python + PIL)"""
import sys
from PIL import Image, ImageDraw
d, out, views = sys.argv[1], sys.argv[2], sys.argv[3:]
ims = []
for v in views:
    try: ims.append((v, Image.open(f"{d}/bigdub_concept_{v}.png").convert("RGB")))
    except Exception as ex: print("missing", v, ex)
cols = 2 if len(ims) <= 4 else 3; rows = (len(ims) + cols - 1) // cols
W, H = 800, 450
sheet = Image.new("RGB", (cols * W, rows * H), (0, 0, 0))
for i, (v, im) in enumerate(ims):
    im = im.resize((W, H), Image.LANCZOS); ImageDraw.Draw(im).text((10, 10), v, fill=(255, 255, 0)); sheet.paste(im, ((i % cols) * W, (i // cols) * H))
    im.save(f"{d}/bigdub_concept_{v}.jpg", quality=88)
sheet.save(out, quality=88); print("sheet", out, sheet.size)
