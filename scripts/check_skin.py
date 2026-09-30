#!/usr/bin/env python3
"""Check a Blender-exported .glb before it goes on the headset: will the mod load it, and will it move with you?

usage: python scripts/check_skin.py SKIN.glb [SKIN2.glb ...] [--push] [--activate]
  --push      also copy the file(s) to the headset (tribemod/skins/) with adb
  --activate  make the (last) file the active skin (writes tribemod/active_skin.txt)

Mirrors what the mod does: glTFRuntime loads mesh 0 with skin 0 (so mesh 0 must be skinned), and the body-tracking
retarget drives bones BY NAME (RPM/Mixamo names; a "prefix:" such as "mixamorig:" is ignored). Exit code 1 if any FAIL.
"""
import json
import math
import os
import struct
import subprocess
import sys

# bones the retarget drives (keep in sync with g_bm in hook/dumper.cpp), with the parent each one must hang from
DRIVEN = [("Hips", None), ("Spine", "Hips"), ("Spine1", "Spine"), ("Spine2", "Spine1"), ("Neck", "Spine2"), ("Head", "Neck")]
for s in ("Left", "Right"):
    DRIVEN += [(s + "Shoulder", "Spine2"), (s + "Arm", s + "Shoulder"), (s + "ForeArm", s + "Arm"), (s + "Hand", s + "ForeArm"),
               (s + "UpLeg", "Hips"), (s + "Leg", s + "UpLeg"), (s + "Foot", s + "Leg"), (s + "ToeBase", s + "Foot")]
HELPERS = ["LeftHandMiddle1", "RightHandMiddle1"]      # hand direction at calibration
OPTIONAL = ["LeftEye", "RightEye"]                     # eye height -> the avatar is scaled to your eye height
ADB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "platform-tools", "adb.exe")
REMOTE = "/sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod"

COMP = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Report:
    def __init__(self):
        self.lines, self.fails, self.warns, self.nomove, self.partial = [], 0, 0, False, False

    def add(self, tag, msg, move=False):
        """move=True: the problem only affects body tracking (the skin still loads and follows you, stiff)."""
        self.lines.append("  [%s] %s" % (tag, msg))
        if move:
            self.nomove |= tag == "FAIL"
            self.partial |= tag == "WARN"
        else:
            self.fails += tag == "FAIL"
            self.warns += tag == "WARN"


def short(name):
    return name.split(":")[-1] if name else name


def load_glb(path):
    d = open(path, "rb").read()
    magic, ver, length = struct.unpack_from("<4sII", d, 0)
    if magic != b"glTF" or ver != 2:
        raise ValueError("not a glTF 2.0 binary (.glb)")
    off, js, binc = 12, None, b""
    while off < len(d):
        clen, ctype = struct.unpack_from("<II", d, off)
        chunk = d[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            binc = chunk
        off += 8 + clen
    return js, binc, len(d)


def read_accessor(js, binc, idx):
    a = js["accessors"][idx]
    bv = js["bufferViews"][a["bufferView"]]
    fmt, size = COMP[a["componentType"]]
    n = NCOMP[a["type"]]
    stride = bv.get("byteStride", size * n)
    base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    out = []
    for i in range(a["count"]):
        vals = struct.unpack_from("<%d%s" % (n, fmt), binc, base + i * stride)
        if a.get("normalized"):
            mx = {"B": 255.0, "H": 65535.0, "b": 127.0, "h": 32767.0}[fmt]
            vals = tuple(v / mx for v in vals)
        out.append(vals)
    return out


def mat_trs(n):
    if "matrix" in n:
        m = n["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = n.get("translation", [0, 0, 0])
    x, y, z, w = n.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = n.get("scale", [1, 1, 1])
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx], [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
            [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz], [0, 0, 0, 1]]


def mmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def is_identity(n):
    if "matrix" in n:
        return all(abs(v - (1.0 if i % 5 == 0 else 0.0)) < 1e-4 for i, v in enumerate(n["matrix"]))
    return (all(abs(v) < 1e-4 for v in n.get("translation", [0, 0, 0])) and
            all(abs(a - b) < 1e-4 for a, b in zip(n.get("rotation", [0, 0, 0, 1]), [0, 0, 0, 1])) and
            all(abs(v - 1) < 1e-4 for v in n.get("scale", [1, 1, 1])))


def check(path):
    rep = Report()
    print("\n=== %s ===" % path)
    try:
        js, binc, fsize = load_glb(path)
    except Exception as e:
        rep.add("FAIL", "can't read: %s -- export as glTF Binary (.glb)" % e)
        print("\n".join(rep.lines))
        return rep
    nodes = js.get("nodes", [])
    meshes, skins = js.get("meshes", []), js.get("skins", [])
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}

    # --- loadability: mesh 0 must be the skinned body, skin 0 its armature ---
    rep.add("INFO", "file %.1f MB, %d mesh(es), %d skin(s), %d material(s), %d image(s), %d animation(s)" % (
        fsize / 1e6, len(meshes), len(skins), len(js.get("materials", [])), len(js.get("images", [])), len(js.get("animations", []))))
    if fsize > 30e6:
        rep.add("WARN", "big file: slow to load on Quest (shrink textures to 1024-2048 px)")
    if not meshes or not skins:
        rep.add("FAIL", "no %s: the loader needs one mesh skinned to an armature (Ctrl+P > Armature Deform)" % ("mesh" if not meshes else "skin"))
        print("\n".join(rep.lines))
        return rep
    prims = meshes[0].get("primitives", [])
    if not all("JOINTS_0" in p.get("attributes", {}) and "WEIGHTS_0" in p.get("attributes", {}) for p in prims):
        rep.add("FAIL", "mesh 0 ('%s') isn't skinned (no JOINTS_0/WEIGHTS_0): parent it to the armature with Armature Deform" % meshes[0].get("name"))
    if len(meshes) > 1:
        rep.add("WARN", "%d meshes: only mesh 0 ('%s') is loaded -- join the body parts into one mesh (Ctrl+J)" % (len(meshes), meshes[0].get("name")))
    tris = 0
    for p in prims:
        if "indices" in p:
            tris += js["accessors"][p["indices"]]["count"] // 3
        else:
            tris += js["accessors"][p["attributes"]["POSITION"]]["count"] // 3
    rep.add("WARN" if tris > 60000 else "OK", "%d triangles%s" % (tris, " -- heavy for Quest; aim for < 50k" if tris > 60000 else ""))
    # unweighted vertices collapse to the origin
    zero, total = 0, 0
    for p in prims:
        at = p.get("attributes", {})
        if "WEIGHTS_0" in at:
            ws = read_accessor(js, binc, at["WEIGHTS_0"])
            total += len(ws)
            zero += sum(1 for w in ws if sum(w) < 1e-3)
        if "JOINTS_1" in at:
            rep.add("WARN", "more than 4 bone influences per vertex (JOINTS_1): limit to 4 in the export settings")
    if zero:
        rep.add("FAIL", "%d of %d vertices have no bone weights (they'll collapse): Weight Paint / Automatic Weights" % (zero, total))
    elif total:
        rep.add("OK", "all %d vertices weighted" % total)
    for i, m in enumerate(js.get("materials", [])):
        if m.get("alphaMode") == "BLEND":
            rep.add("WARN", "material '%s' uses alpha BLEND: may sort badly; use OPAQUE or MASK" % m.get("name"))
    for img in js.get("images", []):
        if "uri" in img and not img["uri"].startswith("data:"):
            rep.add("WARN", "texture '%s' is an external file: export as .glb so textures are embedded" % img["uri"])
    if "morphTargets" in str(meshes[0].get("primitives", [])) or any("targets" in p for p in prims):
        rep.add("INFO", "has shape keys (morph targets): loaded but unused")

    # --- skeleton: names, hierarchy, transforms ---
    joints = skins[0]["joints"]
    jset = set(joints)
    names = {short(nodes[j].get("name", "")): j for j in joints}
    prefixed = [nodes[j].get("name") for j in joints if ":" in nodes[j].get("name", "")]
    if prefixed:
        rep.add("INFO", "bone names have a prefix ('%s'): fine, the mod ignores it" % prefixed[0].split(":")[0])
    roots = [j for j in joints if parent.get(j) not in jset]
    rep.add("OK" if len(roots) == 1 else "WARN", "%d bones, root bone%s: %s" % (
        len(joints), "" if len(roots) == 1 else "s (expect 1)", ", ".join(nodes[r].get("name", "?") for r in roots)))
    anc = parent.get(roots[0]) if roots else None
    while anc is not None:
        if not is_identity(nodes[anc]):
            rep.add("WARN", "armature object '%s' has a transform (rotation/scale): in Blender select it and Ctrl+A > All Transforms before export"
                    % nodes[anc].get("name"))
        anc = parent.get(anc)
    for j in joints:
        s = nodes[j].get("scale", [1, 1, 1])
        if min(s) < 0 or max(abs(v - 1) for v in s) > 0.01:
            rep.add("WARN", "bone '%s' has scale %s: apply scale in Blender (bones should be scale 1)" % (nodes[j].get("name"), s))
    missing = [b for b, _ in DRIVEN if b not in names]
    if missing:
        heavy = any(b in missing for b in ("LeftArm", "RightArm", "Head"))
        rep.add("FAIL" if heavy else "WARN", "missing bones %s: %s" % (
            ", ".join(missing), "the body can't be driven (a half-body or non-RPM rig: it will follow you, stiff)" if heavy else "those parts won't move"), move=True)
    else:
        rep.add("OK", "all %d tracked bones present (Hips..Head, arms, legs)" % len(DRIVEN))
    for b, p in DRIVEN:
        if b in names and p and p in names:
            actual = parent.get(names[b])
            if actual != names[p]:
                pn = short(nodes[actual].get("name", "")) if actual is not None else "(none)"
                tag = "WARN" if b in ("LeftHand", "RightHand", "LeftForeArm", "RightForeArm") else "INFO"
                rep.add(tag, "'%s' hangs from '%s', expected '%s'%s" % (b, pn, p,
                        " (arm IK needs Arm > ForeArm > Hand directly; wrist pinning is skipped for this arm)" if tag == "WARN" else ""), move=True)
    for h in HELPERS:
        if h not in names:
            rep.add("INFO", "no %s: hand direction at calibration uses the rest pose" % h, move=True)
    # with controllers the model's own hands are shown, posed from Meta's hand tracking data (wrist frame + fingers)
    fingers = [s + "Hand" + f + str(k) for s in ("Left", "Right") for f in ("Thumb", "Index", "Middle", "Ring", "Pinky") for k in (1, 2, 3)]
    missing_f = [f for f in fingers if f not in names]
    if not missing_f:
        rep.add("OK", "all 30 finger bones present (hands + fingers posed while you hold controllers)", move=True)
    else:
        rep.add("WARN", "%d of 30 finger bones missing (e.g. %s): those fingers stay stiff while you hold controllers"
                % (len(missing_f), ", ".join(missing_f[:3])), move=True)

    # --- rest pose geometry (glTF: Y up, character should face +Z; its left is +X) ---
    world = {}

    def wm(i):
        if i not in world:
            world[i] = mmul(wm(parent[i]), mat_trs(nodes[i])) if i in parent else mat_trs(nodes[i])
        return world[i]
    pos = {b: (wm(j)[0][3], wm(j)[1][3], wm(j)[2][3]) for b, j in names.items()}
    pa = prims[0]["attributes"].get("POSITION")
    if pa is not None:
        acc = js["accessors"][pa]
        if "min" in acc and "max" in acc:
            rep.add("INFO", "mesh height %.2f m" % (acc["max"][1] - acc["min"][1]))
    if "Hips" in pos and "Head" in pos:
        torso = math.sqrt(sum((pos["Head"][i] - pos["Hips"][i]) ** 2 for i in range(3)))
        if not 0.25 < torso < 1.2:
            rep.add("FAIL", "Hips-to-Head is %.3g units (a human is ~0.5-0.7 m): wrong units -- export in meters, apply scale in Blender" % torso)
        else:
            rep.add("OK", "units look right (Hips-to-Head %.2f m)" % torso)
    if "LeftArm" in pos and "RightArm" in pos:
        lx = pos["LeftArm"][0] - pos["RightArm"][0]
        lz = pos["LeftArm"][2] - pos["RightArm"][2]
        facing = math.degrees(math.atan2(-lz, lx))   # 0 = faces +Z (glTF front)
        if abs(facing) > 60:
            rep.add("WARN" if abs(facing) < 120 else "FAIL", "LeftArm is on the character's %s (facing %+.0f deg from +Z): %s" % (
                "right" if abs(facing) > 120 else "side", facing,
                "Left/Right bone names are swapped (mirror the names)" if abs(facing) > 120 else "rotate the model to face -Y in Blender (glTF +Z)"), move=True)
        else:
            rep.add("OK", "faces front (+Z), LeftArm on its left")
    if "LeftArm" in pos and "LeftForeArm" in pos:
        d = [pos["LeftForeArm"][i] - pos["LeftArm"][i] for i in range(3)]
        el = math.degrees(math.asin(d[1] / max(1e-9, math.sqrt(sum(v * v for v in d)))))
        kind = "T-pose" if abs(el) < 20 else ("A-pose" if el < -20 else "arms raised")
        rep.add("OK" if kind != "arms raised" else "WARN", "rest pose: %s (upper arm %+.0f deg); the mod handles T or A" % (kind, el))
    feet = [pos[b][1] for b in ("LeftToeBase", "RightToeBase", "LeftFoot", "RightFoot") if b in pos]
    eyes = [pos[b][1] for b in OPTIONAL if b in pos]
    if feet:
        sole = min(feet) - 0.02
        if eyes:
            eh = sum(eyes) / len(eyes) - sole
            rep.add("OK", "eye height %.2f m -> in-game scale for a 1.63 m eye height: %.2f" % (eh, 1.63 / eh if eh > 0.3 else 0))
        elif "Head" in pos:
            rep.add("INFO", "no LeftEye/RightEye: scale uses Head + 8 cm as eye height (add eye bones for an exact fit)")
    print("\n".join(rep.lines))
    print("  => LOADS: %s" % ("NO, fix the FAIL items" if rep.fails else ("yes, with warnings" if rep.warns else "yes")))
    print("  => MOVES WITH YOU: %s" % ("no (follows you, stiff)" if rep.nomove or rep.fails else ("partly" if rep.partial else "yes")))
    return rep


def adb(*args):
    return subprocess.run([ADB] + list(args), capture_output=True, text=True, env=dict(os.environ, MSYS_NO_PATHCONV="1"))


def main():
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2
    reps = [check(f) for f in files]
    bad = any(r.fails for r in reps)
    if "--push" in sys.argv or "--activate" in sys.argv:
        if bad:
            print("\nnot pushing: it won't load -- fix the FAIL items first")
            return 1
        for f in files:
            r = adb("push", f, REMOTE + "/skins/" + os.path.basename(f))
            print("push %s: %s" % (os.path.basename(f), (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "?"))
        if "--activate" in sys.argv:
            name = os.path.basename(files[-1])
            r = adb("shell", "echo -n %s > %s/active_skin.txt" % (name, REMOTE))
            print("active skin -> %s %s" % (name, "(relaunch Tribe, or switch skins in-game)" if r.returncode == 0 else "FAILED: " + r.stderr.strip()))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
