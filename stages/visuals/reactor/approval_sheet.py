"""Approval sheets from the full-res stills in renders/approval/ (system Python 3 + Pillow).

  python approval_sheet.py [--out DIR] [--tile 640]

Four sheets, one per group (core, plant, science, sting + opener), each concept a row of its variants, every tile
numbered (1a, 1b, ...) so the user can answer per tile. A missing still shows as a grey tile with the reason: the gate's
RESULT line if its look-dev failed, else "not rendered yet".
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "renders", "approval")

GROUPS = [
    ("core", [("1", "cherenkov_pool", "Cherenkov Pool", ("blue", "uv", "deep")),
              ("2", "control_rods", "Control Rods", ("amber", "cyan", "red")),
              ("3", "chain_reaction", "Chain Reaction", ("cyan", "amber", "magenta")),
              ("4", "meltdown", "Meltdown", ("ember", "alarm", "scram"))]),
    ("plant", [("5", "cooling_towers", "Cooling Towers", ("teal", "orange", "purple")),
               ("6", "turbine_hall", "Turbine Hall", ("amber", "blue", "green")),
               ("7", "coolant_pipes", "Coolant Pipes", ("cyan", "amber", "uv")),
               ("8", "containment", "Containment", ("red", "amber", "breach"))]),
    ("science", [("9", "particle_ring", "Particle Ring", ("magenta", "cyan", "green")),
                 ("10", "geiger_scope", "Geiger Scope", ("green", "amber", "cyan")),
                 ("11", "isotope_lattice", "Isotope Lattice", ("uv", "gold", "cyan")),
                 ("12", "hazard_type", "Hazard Type", ("amber", "red", "blue"))]),
    ("sting_opener", [("S", "sting", "Reactor Sting (4 bars)", ("amber", "blue", "red")),
                      ("O", "cold_start", "Cold Start (the opener)", ("blue",))]),
]


def missing_reason(name):
    gate = os.path.join(APP, f"{name}_gate.txt")
    if os.path.exists(gate):
        for line in open(gate, encoding="utf-8", errors="replace"):
            if line.startswith("RESULT") and "PASS" not in line:
                return "gate failed: " + line.split("FAIL:", 1)[-1].strip()
    return "not rendered yet"


def sheet(group, rows, out_dir, tw):
    th = tw * 9 // 16
    pad, lab, head = 8, 26, 44
    cols = max(len(r[3]) for r in rows)
    w = cols * tw + (cols + 1) * pad
    h = head + len(rows) * (th + lab + pad) + pad
    im = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(im)
    big, small = ImageFont.load_default(size=24), ImageFont.load_default(size=17)
    d.text((pad, 10), f"REACTOR visuals: approval stills ({group.replace('_', ' + ')})", fill=(230, 230, 230), font=big)
    have, total = 0, 0
    for r, (num, concept, title, variants) in enumerate(rows):
        for c, var in enumerate(variants):
            name = f"{concept}_{var}"
            tag = num + ("abc"[c] if len(variants) > 1 else "")
            x = pad + c * (tw + pad)
            y = head + r * (th + lab + pad)
            png = os.path.join(APP, f"{name}.png")
            total += 1
            if os.path.exists(png):
                im.paste(Image.open(png).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
                have += 1
                note = ""
            else:
                d.rectangle([x, y, x + tw - 1, y + th - 1], fill=(38, 38, 38))
                note = missing_reason(name)
                d.text((x + 16, y + th // 2 - 10), note, fill=(200, 120, 90), font=small)
            d.text((x + 2, y + th + 4), f"{tag}  {title} · {var}", fill=(220, 220, 220), font=small)
    out = os.path.join(out_dir, f"approval_{group}.jpg")
    im.save(out, quality=88)
    return out, have, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=APP)
    ap.add_argument("--tile", type=int, default=640)
    a = ap.parse_args()
    for group, rows in GROUPS:
        out, have, total = sheet(group, rows, a.out, a.tile)
        print(f"{out}: {have}/{total} stills")


if __name__ == "__main__":
    main()
