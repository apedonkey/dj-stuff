"""hdr_to_png.py <dir> [--keep]: every Radiance .hdr in <dir> (bigdub_views.py's linear scene colour) to an sRGB PNG beside it,
as the Quest shows the unlit emissive (no tonemapping, an sRGB framebuffer: clip at 1, then the sRGB curve). Prints each
picture's linear mean and 99.9th percentile (an all-black picture fails: exit 1). Removes the .hdr unless --keep.

    python -P -B hdr_to_png.py <dir>
"""
import os
import re
import sys

import numpy as np
from PIL import Image


def read_hdr(path):
    with open(path, "rb") as f:
        data = f.read()
    head_end = data.index(b"\n\n") + 2
    m = re.search(rb"-Y (\d+) \+X (\d+)\n", data[head_end:head_end + 64])
    h, w = int(m.group(1)), int(m.group(2))
    p = head_end + m.end()
    out = np.zeros((h, w, 4), np.uint8)
    buf = np.frombuffer(data, np.uint8)
    for y in range(h):
        if buf[p] == 2 and buf[p + 1] == 2 and (buf[p + 2] << 8 | buf[p + 3]) == w:    # new RLE scanline
            p += 4
            for c in range(4):
                x = 0
                while x < w:
                    n = int(buf[p]); p += 1
                    if n > 128:
                        n -= 128
                        out[y, x:x + n, c] = buf[p]; p += 1
                    else:
                        out[y, x:x + n, c] = buf[p:p + n]; p += n
                    x += n
        else:                                                                     # flat RGBE
            out[y] = buf[p:p + 4 * w].reshape(w, 4); p += 4 * w
    e = out[..., 3].astype(np.int32)
    scale = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0)
    return out[..., :3].astype(np.float64) * scale[..., None]


def srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def main():
    d = sys.argv[1]
    bad = 0
    for name in sorted(os.listdir(d)):
        if not name.endswith(".hdr"):
            continue
        lin = read_hdr(os.path.join(d, name))
        png = os.path.join(d, name[:-4] + ".png")
        Image.fromarray((srgb(lin) * 255.0 + 0.5).astype(np.uint8)).save(png)
        mean, p999 = float(lin.mean()), float(np.percentile(lin, 99.9))
        print(f"[HDR] {name} -> {os.path.basename(png)}: {lin.shape[1]} x {lin.shape[0]}, linear mean {mean:.4f}, "
              f"p99.9 {p999:.3f}")
        bad += lin.max() <= 0.0
        if "--keep" not in sys.argv:
            os.remove(os.path.join(d, name))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
