"""make_obb.py <out.obb> <pak> [<pak> ...]: Tribe's patch OBB = a STORED zip of paks under TribeXR/Content/Paks/ with the
main OBB's comment ("      2304"). Several paks can ride in one OBB (each chunk mounts on its own)."""
import os
import sys
import zipfile

obb, paks = sys.argv[1], sys.argv[2:]
with zipfile.ZipFile(obb, "w", compression=zipfile.ZIP_STORED) as z:
    for p in paks:
        z.write(p, "TribeXR/Content/Paks/" + os.path.basename(p))
    z.comment = b"      2304"
z = zipfile.ZipFile(obb)
for i in z.infolist():
    print("obb entry:", i.filename, "stored" if i.compress_type == 0 else i.compress_type, i.file_size)
print("obb comment:", repr(z.comment))
