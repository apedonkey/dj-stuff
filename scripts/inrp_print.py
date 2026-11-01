#!/usr/bin/env python3
"""Read Tribe XR's input-replay files (.inrp: the lessons' recorded hands, head and controller input).

    python -I scripts/inrp_print.py <file.inrp | folder> [--frames N] [--keys]

The layout was read from libUnreal.so (build 2304): InputReplayComponent::LoadReplay (Ghidra 0x51ae3a0) loads the file
into memory and runs one serializer (0x51e7588) over the replay struct; StopRecording saves with the same function.
All integers are little-endian.

    int32   version                 must be 2 (the loader fails otherwise)
    int32   frame count, then each frame (0x51e7840):
        float   time                seconds since recording started
        int32   n, n x transform    world transforms     (component's ComponentToWorld; SetWorldLocationAndRotation)
        int32   n, n x transform    relative transforms  (SetRelativeLocationAndRotation)
        int32   n, n x uint8        keys pressed this frame   (byte code -> FKey through a table in the binary)
        int32   n, n x uint8        keys released this frame
        int32   n, n x (uint8 code, float value)   axis values (5 bytes each on disk)
    int32   timestamp count, n x float   timestamps (seconds; they fire OnTimestampTriggered during playback)

    transform = quantized vector + compressed rotator
    quantized vector (UE 5.4 WriteQuantizedVector, scale 10): uint32 info; bits = info & 63, flag = info >> 6 & 1;
        bits > 0: three components, each ceil(bits/8) bytes, masked to `bits` and sign-extended; divide by 10 if flag
        bits = 0: three doubles (flag 1) or floats (flag 0), full precision
    compressed rotator (FRotator::SerializeCompressed): pitch, yaw, roll each = uint8 present (low bit);
        if present, uint8 angle (degrees = byte * 360 / 256)
Positions are in Unreal units (centimetres).
"""
import os
import struct
import sys

# byte code -> Unreal key, from the static tables _INIT_1109 (Ghidra 0x51bbb80) builds at load (read)
KEY_NAMES = [
    "OculusTouch_Left_Trigger_Click", "OculusTouch_Left_Trigger_Touch",
    "OculusTouch_Right_Trigger_Click", "OculusTouch_Right_Trigger_Touch",
    "OculusTouch_Left_Grip_Click", "OculusTouch_Right_Grip_Click",
    "OculusTouch_Right_A_Click", "OculusTouch_Right_A_Touch",
    "OculusTouch_Right_B_Click", "OculusTouch_Right_B_Touch",
    "OculusTouch_Left_X_Click", "OculusTouch_Left_X_Touch",
    "OculusTouch_Left_Y_Click", "OculusTouch_Left_Y_Touch",
    "OculusTouch_Left_Thumbstick_Up", "OculusTouch_Left_Thumbstick_Touch",
    "OculusTouch_Right_Thumbstick_Up", "OculusTouch_Right_Thumbstick_Touch",
]
AXIS_NAMES = [
    "MotionController L TriggerAxis", "MotionController R TriggerAxis",
    "MotionController L GripAxis", "MotionController R GripAxis",
    "MotionController L Thumbstick_Y", "MotionController R Thumbstick_Y",
]
# TribePawn::GetReplayRecordingComponent (0x519a368) records no world components and 4 relative ones; which is which
# is inferred from the data (highest = head, -Y = left, +Y = right, constant = the actor root at pawn +0x1a0)
RELATIVE_NAMES = ["head", "left hand", "right hand", "root"]


def key_name(code):
    return KEY_NAMES[code] if code < len(KEY_NAMES) else f"key{code}"


def axis_name(code):
    return AXIS_NAMES[code] if code < len(AXIS_NAMES) else f"axis{code}"


class Reader:
    def __init__(self, data):
        self.d = data
        self.o = 0

    def take(self, n):
        if self.o + n > len(self.d):
            raise ValueError(f"truncated at offset {self.o} (wanted {n} bytes, file is {len(self.d)})")
        b = self.d[self.o:self.o + n]
        self.o += n
        return b

    def u8(self):
        return self.take(1)[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def f32(self):
        return struct.unpack("<f", self.take(4))[0]

    def count(self, what, limit):
        n = self.i32()
        if n < 0 or n > limit:
            raise ValueError(f"bad {what} count {n} at offset {self.o - 4}")
        return n


def quantized_vector(r, scale=10):
    info = r.u32()
    bits, flag = info & 63, (info >> 6) & 1
    if info >> 7:
        raise ValueError(f"bad quantized-vector header 0x{info:x} at offset {r.o - 4}")
    if bits:
        nbytes = (bits + 7) // 8
        out = []
        for _ in range(3):
            v = int.from_bytes(r.take(nbytes), "little") & ((1 << bits) - 1)
            sign = 1 << (bits - 1)
            v = (v ^ sign) - sign
            out.append(v / scale if flag else float(v))
        return tuple(out), bits
    fmt, size = ("<3d", 24) if flag else ("<3f", 12)
    return struct.unpack(fmt, r.take(size)), 0


def compressed_rotator(r):
    out = []
    for _ in range(3):
        present = r.u8() & 1
        out.append(r.u8() * 360.0 / 256.0 if present else 0.0)
    return tuple(out)  # pitch, yaw, roll in degrees, 0..360


def transform(r):
    loc, bits = quantized_vector(r)
    return loc, compressed_rotator(r), bits


def read_inrp(data):
    r = Reader(data)
    version = r.i32()
    if version != 2:
        raise ValueError(f"version {version}, expected 2")
    frames = []
    for _ in range(r.count("frame", 1 << 24)):
        f = {"time": r.f32()}
        f["world"] = [transform(r) for _ in range(r.count("world transform", 4096))]
        f["relative"] = [transform(r) for _ in range(r.count("relative transform", 4096))]
        f["pressed"] = list(r.take(r.count("pressed key", 1 << 16)))
        f["released"] = list(r.take(r.count("released key", 1 << 16)))
        axes = []
        for _ in range(r.count("axis", 1 << 16)):
            code = r.u8()
            axes.append((code, r.f32()))
        f["axes"] = axes
        frames.append(f)
    timestamps = [r.f32() for _ in range(r.count("timestamp", 1 << 20))]
    return {"version": version, "frames": frames, "timestamps": timestamps, "end": r.o, "size": len(data)}


def summary(path, show_frames=0, show_keys=False):
    rep = read_inrp(open(path, "rb").read())
    fr = rep["frames"]
    print(f"{path}: {len(fr)} frames, {rep['end']} of {rep['size']} bytes read"
          + ("" if rep["end"] == rep["size"] else f"  ({rep['size'] - rep['end']} bytes left over)"))
    if not fr:
        return rep
    times = [f["time"] for f in fr]
    gaps = [b - a for a, b in zip(times, times[1:])]
    back = sum(1 for g in gaps if g < 0)
    print(f"  time {times[0]:.3f} .. {times[-1]:.3f} s; gap min {min(gaps, default=0):.4f} max {max(gaps, default=0):.3f} s"
          f"; {back} backwards steps; timestamps {['%.2f' % t for t in rep['timestamps']]}")
    for kind in ("world", "relative"):
        counts = sorted({len(f[kind]) for f in fr})
        n = max(counts)
        print(f"  {kind}: per-frame counts {counts}")
        for i in range(n):
            locs = [f[kind][i][0] for f in fr if len(f[kind]) > i]
            rots = [f[kind][i][1] for f in fr if len(f[kind]) > i]
            bits = sorted({f[kind][i][2] for f in fr if len(f[kind]) > i})
            rng = " ".join(f"{a}[{min(l[k] for l in locs):8.1f},{max(l[k] for l in locs):8.1f}]" for k, a in enumerate("xyz"))
            label = RELATIVE_NAMES[i] if kind == "relative" and i < len(RELATIVE_NAMES) else ""
            print(f"    #{i} {label}: {len(locs)} samples, cm {rng}, bits {bits}, yaw first {rots[0][1]:.1f}")
    pressed = [k for f in fr for k in f["pressed"]]
    released = [k for f in fr for k in f["released"]]
    axes = [a for f in fr for a in f["axes"]]
    print(f"  keys: {len(pressed)} presses, {len(released)} releases")
    for c in sorted(set(pressed) | set(released)):
        print(f"    {c:2d} {key_name(c)}: {pressed.count(c)} presses, {released.count(c)} releases")
    if axes:
        print(f"  axes: {len(axes)} values")
        for c in sorted({c for c, _ in axes}):
            vals = [v for k, v in axes if k == c]
            print(f"    {c:2d} {axis_name(c)}: {len(vals)} values, range [{min(vals):.2f}, {max(vals):.2f}]")
    if show_keys:
        for f in fr:
            if f["pressed"] or f["released"]:
                print(f"    {f['time']:8.3f} s  pressed {[key_name(k) for k in f['pressed']]}"
                      f"  released {[key_name(k) for k in f['released']]}")
    for f in fr[:show_frames]:
        rel = "  ".join(f"({l[0]:.1f},{l[1]:.1f},{l[2]:.1f})" for l, _, _ in f["relative"])
        print(f"    {f['time']:8.3f} s  world {len(f['world'])}  relative {rel}  axes {f['axes']}")
    return rep


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    show_frames = int(argv[argv.index("--frames") + 1]) if "--frames" in argv else 0
    if "--frames" in argv:
        args.remove(str(show_frames))
    show_keys = "--keys" in argv
    if not args:
        print(__doc__)
        return 2
    paths = []
    for a in args:
        if os.path.isdir(a):
            for root, _, files in os.walk(a):
                paths += [os.path.join(root, f) for f in sorted(files) if f.endswith(".inrp")]
        else:
            paths.append(a)
    bad = 0
    for p in paths:
        try:
            summary(p, show_frames, show_keys)
        except ValueError as e:
            bad += 1
            print(f"{p}: FAILED: {e}")
    if len(paths) > 1:
        print(f"{len(paths)} files, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
