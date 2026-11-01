"""stage_obb.py <live.obb> <new pak> [<new pak> ...] <out.obb>: the stages OBB with one more stage, offline (no adb): every
entry of the live OBB copied byte for byte (a same-named pak is replaced), the new paks added, written the way
scripts/push_obb.sh builds its merge (a STORED zip, entries TribeXR/Content/Paks/<pak> in sorted order, the comment
"      2311" that Tribe 0.12.6 checks). Prints each entry with its size and md5, the OBB's md5, and checks that every
old entry came through unchanged. It never touches the live file.

    python -P -B stage_obb.py C:/Users/Chris/TribeUE/paks_current/patch_live.obb pakchunk56-Android_ASTC_P.pak out.obb
"""
import hashlib
import os
import sys
import zipfile

PREFIX = "TribeXR/Content/Paks/"
COMMENT = b"      2311"


def md5_of(stream):
    h = hashlib.md5()
    for chunk in iter(lambda: stream.read(1 << 22), b""):
        h.update(chunk)
    return h.hexdigest()


def main():
    live, paks, out = sys.argv[1], sys.argv[2:-1], sys.argv[-1]
    if os.path.abspath(out) == os.path.abspath(live):
        sys.exit("refusing to overwrite the live OBB")
    src = zipfile.ZipFile(live)
    old = {i.filename: i for i in src.infolist()}
    print(f"live {live}: comment {src.comment!r}, {len(old)} entries")
    new = {PREFIX + os.path.basename(p): p for p in paks}
    names = sorted(set(old) | set(new))
    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as z:
        for n in names:
            if n in new:
                z.write(new[n], n)
                print(f"  {'replace' if n in old else 'add'} {n}")
            else:
                with src.open(old[n]) as f, z.open(zipfile.ZipInfo(n, date_time=old[n].date_time), "w") as g:
                    for chunk in iter(lambda: f.read(1 << 22), b""):
                        g.write(chunk)
        z.comment = COMMENT
    os.replace(tmp, out)
    z = zipfile.ZipFile(out)
    bad = 0
    for i in z.infolist():
        with z.open(i) as f:
            m = md5_of(f)
        same = ""
        if i.filename in old and i.filename not in new:
            with src.open(old[i.filename]) as f:
                same = " (unchanged)" if md5_of(f) == m else " CHANGED"
            bad += same == " CHANGED"
        print(f"  {i.filename}  {'stored' if i.compress_type == 0 else i.compress_type}  {i.file_size} B  md5 {m}{same}")
    with open(out, "rb") as f:
        print(f"{out}: {os.path.getsize(out)} B, md5 {md5_of(f)}, comment {z.comment!r}")
    sys.exit(1 if bad or z.comment != COMMENT else 0)


if __name__ == "__main__":
    main()
