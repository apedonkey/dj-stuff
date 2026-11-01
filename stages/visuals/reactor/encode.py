"""Encode a rendered PNG frame sequence to the pack's MP4 (system Python 3; ffmpeg on PATH).

  python encode.py FRAMES_DIR PREFIX OUT.mp4 [--frames N] [--bitrate 16M]

H.264 High (level 4.0), yuv420p 8-bit, BT.709 matrix, TV range, tagged bt709 (like the Dino pack's MP4s, which play on
the wall), 1920x1080, 30 fps, no audio, a keyframe every 30 frames (1 s) so players can seek anywhere fast, no
B-frames (the Dino files have none). Two passes at ~16 Mbps (the lead's spec). The frames are 8-bit sRGB PNGs rendered
with the Standard view transform; ffmpeg only converts RGB -> Y'CbCr with the BT.709 matrix (no tone change).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("prefix")
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, help="number of frames (default: all PREFIXnnnn.png)")
    ap.add_argument("--bitrate", default="16M")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.frames_dir, a.prefix + "[0-9][0-9][0-9][0-9].png")))
    n = a.frames or len(files)
    assert n and len(files) >= n, f"{len(files)} frames in {a.frames_dir}, need {n}"
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="rx_encode_")
    common = ["-framerate", "30", "-start_number", "0", "-i", os.path.join(a.frames_dir, a.prefix + "%04d.png"),
              "-frames:v", str(n),
              "-vf", "scale=out_range=tv:out_color_matrix=bt709:flags=lanczos+accurate_rnd+full_chroma_int,"
                     "format=yuv420p",
              "-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-level:v", "4.0",
              "-b:v", a.bitrate, "-maxrate", "20M", "-bufsize", "25M",
              "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", "-bf", "0", "-x264-params", "aq-mode=3",
              "-passlogfile", os.path.join(tmp, "x264"), "-an"]
    tags = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error"] + common + ["-pass", "1", "-f", "null", "-"], check=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error"] + common + ["-pass", "2"] + tags
                       + ["-movflags", "+faststart", out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[VJ] encoded {n} frames -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
