"""Check scan_strings on a buffer with known contents, using tiny chunks to force boundaries.

Run: python tests/test_scan_strings.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import scan_strings as s  # noqa: E402

s.CHUNK, s.OVERLAP = 1000, 100

data = bytearray(5000)
placed = {
    10: b"https://models.readyplayer.me/abc123.glb",
    985: b"AvatarLoaderComponent",                   # straddles the 1000-byte chunk boundary
    2000: "UReadyPlayerMeAvatar".encode("utf-16-le"),
    3000: b"rpm",                                   # 3 chars: below the strings minimum, must be dropped
    3100: b"TurntableRPM",
    4000: b"model.gltf",
}
for offset, raw in placed.items():
    data[offset:offset + len(raw)] = raw

hits = []
s.scan_stream(io.BytesIO(bytes(data)).read, hits.append)
got = sorted((h["offset"], h["enc"], h["text"], tuple(h["terms"])) for h in hits)
expected = [
    (10, "ascii", "https://models.readyplayer.me/abc123.glb", ("readyplayer", ".glb")),
    (985, "ascii", "AvatarLoaderComponent", ("avatarloader", "avatar")),
    (2000, "utf16le", "UReadyPlayerMeAvatar", ("readyplayer", "avatar")),
    (3100, "ascii", "TurntableRPM", ("rpm",)),
    (4000, "ascii", "model.gltf", ("gltf",)),
]
for row in got:
    print(row)
assert got == expected, f"mismatch:\n got      {got}\n expected {expected}"
print("OK: all 5 expected hits, no duplicates, 3-char 'rpm' dropped")
