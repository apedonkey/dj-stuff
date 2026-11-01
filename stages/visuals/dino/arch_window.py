"""Export the Dino Stage arch screen's visible window in video-frame pixels (Blender's Python for mathutils; no render).

  blender.exe -b --factory-startup --python arch_window.py

The stage maps the 16:9 video onto arch.video_box(), a box around the arch-shaped screen (arch.screen_outline()), so
only the part of each frame inside the outline ever shows on the Dino Stage. Writes scripts/arch_window.json with the
outline in 1920x1080 frame pixels (x right, y down), the video box and the visible row band; contact_sheet.py draws it
on every sheet. arch.py is read live: re-run this whenever the arch changes (contact_sheet.py warns when arch.py is
newer than the JSON).
"""
import json
import os
import sys

STAGE_BLENDER = r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender"
sys.dont_write_bytecode = True                   # read-only use of the stage scripts: no __pycache__ under TribeXR
sys.path.insert(0, STAGE_BLENDER)
import arch  # noqa: E402

W, H = 1920, 1080
x0, z0, w, h = arch.video_box()
outline = [((x - x0) / w * W, (1.0 - (z - z0) / h) * H) for x, z in arch.screen_outline()]
ys = [y for _, y in outline]
out = {
    "outline_px": [[round(x, 2), round(y, 2)] for x, y in outline],
    "video_box_m": [x0, z0, w, h],
    "rows_visible": [round(min(ys), 1), round(max(ys), 1)],
    "arch_py": os.path.join(STAGE_BLENDER, "arch.py"),
    "arch_py_mtime": os.path.getmtime(os.path.join(STAGE_BLENDER, "arch.py")),
}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arch_window.json")
with open(path, "w") as fh:
    json.dump(out, fh, indent=1)
print(f"[VJ] arch window: rows {out['rows_visible'][0]:.0f}..{out['rows_visible'][1]:.0f} of {H}, "
      f"{len(outline)} outline points -> {path}", flush=True)
