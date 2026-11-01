"""Encode a rendered PNG frame sequence to an H.264 MP4 with Blender's FFMPEG output (VSE pass-through).

  blender.exe -b --factory-startup --python encode.py -- --frames DIR --prefix spine_tunnel_ --out FILE.mp4 [--crf HIGH]

The sequencer passes the 8-bit sRGB PNGs through untouched (Standard view transform, no compositing): the MP4 shows
exactly the rendered frames. 30 fps, yuv420p, keyframe every 30 frames (1 s) so VJ software can seek anywhere fast.
"""
import glob
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


frames_dir, prefix, out = arg("--frames"), arg("--prefix", ""), os.path.abspath(arg("--out"))
files = sorted(glob.glob(os.path.join(frames_dir, prefix + "[0-9][0-9][0-9][0-9].png")))
assert files, f"no frames in {frames_dir}"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1920, 1080, 100
scene.render.fps, scene.render.fps_base = 30, 1.0
scene.frame_start, scene.frame_end = 0, len(files) - 1
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.sequencer_colorspace_settings.name = "sRGB"
scene.render.use_sequencer, scene.render.use_compositing = True, False

se = scene.sequence_editor_create()
strips = getattr(se, "strips", None) or se.sequences
strip = strips.new_image(name="frames", filepath=files[0], channel=1, frame_start=0)
for f in files[1:]:
    strip.elements.append(os.path.basename(f))
strip.colorspace_settings.name = "sRGB"

r = scene.render
r.image_settings.file_format = "FFMPEG"
ff = r.ffmpeg
ff.format, ff.codec = "MPEG4", "H264"
ff.constant_rate_factor = arg("--crf", "HIGH")
ff.ffmpeg_preset = "GOOD"
ff.gopsize = 30
ff.audio_codec = "NONE"
r.use_file_extension = False
os.makedirs(os.path.dirname(out), exist_ok=True)
r.filepath = out
bpy.ops.render.render(animation=True)
print(f"[VJ] encoded {len(files)} frames -> {out}", flush=True)
