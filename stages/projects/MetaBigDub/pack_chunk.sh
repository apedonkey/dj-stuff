#!/usr/bin/env bash
# pack_chunk.sh <chunk> [out_dir] -- stage every file the cooker's chunk manifest lists for pakchunk<chunk> (packages +
# the chunk's shader library) and repak it (V11, mount ../../../) -> <out_dir>/pakchunk<chunk>-Android_ASTC_P.pak.
# Same staging as the mod project's pack_festival.sh; combine paks into the patch OBB with make_obb.py.
set -euo pipefail
CHUNK="$1"
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
COOK="$PROJ/Saved/Cooked/Android_ASTC/TribeXR"
MANIFEST="$COOK/Metadata/ChunkManifest/pakchunk$CHUNK.txt"
SHADERSRC="$COOK/Metadata/ShaderLibrarySource"
OUT="${2:-$PROJ/Saved/ModPak}"
STAGE="$OUT/stage$CHUNK"
PAK="$OUT/pakchunk$CHUNK-Android_ASTC_P.pak"
[ -f "$MANIFEST" ] || { echo "no chunk manifest: $MANIFEST (cook first)"; exit 1; }
rm -rf "$STAGE"; mkdir -p "$STAGE"
n=0
while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%$'\r'}"; [ -n "$line" ] || continue
    w="$(cygpath -u "$line")"
    rel="${w#"$COOK"/}"
    if [[ "$rel" == Content/ShaderArchive-* ]]; then
        src="$SHADERSRC/${rel#Content/}"
        mkdir -p "$STAGE/TribeXR/Content"; cp "$src" "$STAGE/TribeXR/Content/"; n=$((n+1)); continue
    fi
    for f in "$w".*; do
        [ -f "$f" ] || continue
        d="$STAGE/TribeXR/$(dirname "${f#"$COOK"/}")"; mkdir -p "$d"; cp "$f" "$d/"; n=$((n+1))
    done
done < "$MANIFEST"
echo "staged $n files"
find "$STAGE" -type f | sed "s#$STAGE/##"
rm -f "$PAK"
repak pack --version V11 "$STAGE" "$PAK"
echo "pak ready: $PAK"
