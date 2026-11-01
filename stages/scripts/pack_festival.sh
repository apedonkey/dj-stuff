#!/usr/bin/env bash
# pack_festival.sh -- turn the cooked chunk-50 content into Tribe's patch OBB.
#   1. stage every file the cooker's chunk manifest lists for pakchunk50 (level + materials + the chunk's shader library)
#   2. repak V11 (mount ../../../, the same layout as Tribe's own paks) -> pakchunk50-Android_ASTC_P.pak
#   3. wrap it in a STORED zip with the main OBB's comment ("      2304") -> patch.2304.com.TribeXR.TribeXR.obb
#   4. verify with the tribe-hack repo's pak reader (the same code that parsed Tribe's real paks)
# Usage: bash Scripts/pack_festival.sh [out_dir]      (run after the cook; push the OBB with adb afterwards)
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
COOK="$PROJ/Saved/Cooked/Android_ASTC/TribeXR"
MANIFEST="$COOK/Metadata/ChunkManifest/pakchunk50.txt"
SHADERSRC="$COOK/Metadata/ShaderLibrarySource"
REPO="/c/Users/Chris/OneDrive/Desktop/tribe hack"
OUT="${1:-$PROJ/Saved/ModPak}"
STAGE="$OUT/stage"
PAK="$OUT/pakchunk50-Android_ASTC_P.pak"
OBB="$OUT/patch.2304.com.TribeXR.TribeXR.obb"

[ -f "$MANIFEST" ] || { echo "no chunk manifest: $MANIFEST (cook first)"; exit 1; }
rm -rf "$STAGE"; mkdir -p "$STAGE"
n=0
while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%$'\r'}"; [ -n "$line" ] || continue
    w="$(cygpath -u "$line")"                       # manifest lists cooked paths without extensions (packages) or full files
    rel="${w#"$COOK"/}"                              # Content/Mods/Festival/... or Content/ShaderArchive-...
    if [[ "$rel" == Content/ShaderArchive-* ]]; then
        src="$SHADERSRC/${rel#Content/}"
        mkdir -p "$STAGE/TribeXR/Content"; cp "$src" "$STAGE/TribeXR/Content/"; n=$((n+1)); continue
    fi
    for f in "$w".*; do                              # package -> its .umap/.uasset/.uexp/.ubulk files
        [ -f "$f" ] || continue
        d="$STAGE/TribeXR/$(dirname "${f#"$COOK"/}")"; mkdir -p "$d"; cp "$f" "$d/"; n=$((n+1))
    done
done < "$MANIFEST"
echo "staged $n files"
find "$STAGE" -type f | sed "s#$STAGE/##"

rm -f "$PAK"
repak pack --version V11 "$STAGE" "$PAK"
repak list "$PAK"

python - "$(cygpath -w "$PAK")" "$(cygpath -w "$OBB")" <<'EOF'
import sys, zipfile
pak, obb = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(obb, "w", compression=zipfile.ZIP_STORED) as z:
    z.write(pak, "TribeXR/Content/Paks/pakchunk50-Android_ASTC_P.pak")
    z.comment = b"      2304"
z = zipfile.ZipFile(obb)
for i in z.infolist():
    print("obb entry:", i.filename, "stored" if i.compress_type == 0 else i.compress_type, i.file_size)
print("obb comment:", repr(z.comment))
EOF
python "$REPO/scripts/pak_list.py" "$(cygpath -w "$OBB")" "$(cygpath -w "$OUT/patch_paklist.txt")" | tail -2
echo "OBB ready: $OBB"
