#!/usr/bin/env python3
"""Find avatar-related strings in binaries: the equivalent of `strings -a -n 4` (ASCII) plus
`strings -a -n 4 -el` (UTF-16LE), filtered with a case-insensitive grep, keeping neighbouring
strings as context.

Terms are matched in the raw bytes and each match is expanded to the printable string that
contains it. Zip containers (APK, OBB, nested .zip/.jar) are scanned entry by entry without
being extracted.

Usage: python scripts/scan_strings.py OUT_DIR INPUT [INPUT ...]
Writes OUT_DIR/hits.tsv, hits_context.txt, unique_<term>.txt and SUMMARY.md.
"""
import collections
import io
import os
import re
import sys
import zipfile

TERMS = ["readyplayer", "rpm", ".glb", "gltf", "avatarloader", "avatar"]
MIN_CHARS = 4                  # same default as `strings`
CHUNK = 64 << 20
OVERLAP = 64 << 10             # longest string that can straddle a chunk boundary
CONTEXT_BYTES = 256            # window searched for neighbouring strings
CONTEXT_STRINGS = 3            # neighbours kept on each side of a hit
MAX_SHOWN = 400                # characters of a string written to the reports
NESTED_ZIP_EXT = (".zip", ".jar", ".apk", ".aar")
MEDIA_EXT = (".wav", ".mp3", ".ogg", ".mp4", ".png", ".jpg", ".jpeg", ".ktx", ".astc", ".ttf", ".otf")

PRINTABLE = frozenset(range(0x20, 0x7F)) | {0x09}
# Buffers are lower-cased before matching, so the patterns are lower-case literals.
HIT = {
    "ascii": re.compile(b"|".join(re.escape(t.encode()) for t in TERMS)),
    "utf16le": re.compile(b"|".join(b"".join(re.escape(bytes([c])) + b"\x00" for c in t.encode())
                                    for t in TERMS)),
}
RUN = {
    "ascii": re.compile(rb"[\t\x20-\x7e]{%d,}" % MIN_CHARS),
    "utf16le": re.compile(rb"(?:[\t\x20-\x7e]\x00){%d,}" % MIN_CHARS),
}


def expand(buf, s, e, enc):
    """Grow [s, e) to the whole printable run around it."""
    if enc == "ascii":
        while s > 0 and buf[s - 1] in PRINTABLE:
            s -= 1
        while e < len(buf) and buf[e] in PRINTABLE:
            e += 1
    else:
        while s >= 2 and buf[s - 1] == 0 and buf[s - 2] in PRINTABLE:
            s -= 2
        while e + 1 < len(buf) and buf[e] in PRINTABLE and buf[e + 1] == 0:
            e += 2
    return s, e


def decode(raw, enc):
    return raw.decode("latin-1") if enc == "ascii" else raw.decode("utf-16-le", "replace")


def neighbours(buf, s, e):
    lo, hi = max(0, s - CONTEXT_BYTES), min(len(buf), e + CONTEXT_BYTES)
    runs = []
    for enc, rx in RUN.items():
        for m in rx.finditer(buf, lo, hi):
            if m.end() <= s or m.start() >= e:
                runs.append((m.start(), m.end(), decode(m.group(), enc)))
    runs.sort()
    before = [r[2] for r in runs if r[1] <= s][-CONTEXT_STRINGS:]
    after = [r[2] for r in runs if r[0] >= e][:CONTEXT_STRINGS]
    return before, after


def scan_buffer(buf, base, lo, hi, emit, seen):
    lowered = buf.lower()
    for enc, rx in HIT.items():
        for m in rx.finditer(lowered, lo - base):
            if m.start() >= hi - base:
                break
            s, e = expand(buf, m.start(), m.end(), enc)
            if (enc, base + s) in seen:
                continue
            seen.add((enc, base + s))
            text = decode(buf[s:e], enc)
            if len(text) < MIN_CHARS:
                continue
            terms = [t for t in TERMS if t in text.lower()]
            before, after = neighbours(buf, s, e)
            emit({"offset": base + s, "enc": enc, "terms": terms, "text": text,
                  "before": before, "after": after})


def scan_stream(read, emit):
    """Scan a byte stream in overlapping chunks; each match is handled exactly once."""
    buf, base, owned_from, seen = b"", 0, 0, set()
    while True:
        data = read(CHUNK)
        buf += data
        owned_to = base + len(buf) - (0 if not data else OVERLAP)
        if owned_to > owned_from:
            scan_buffer(buf, base, owned_from, owned_to, emit, seen)
            owned_from = owned_to
        if not data:
            return
        if len(buf) > 2 * OVERLAP:
            drop = len(buf) - 2 * OVERLAP
            buf, base = buf[drop:], base + drop
            seen = {k for k in seen if k[1] >= base}


def scan_zip(zf, source, prefix, emit, counts):
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = prefix + info.filename
        counts["entries"] += 1
        counts["bytes"] += info.file_size
        if info.filename.lower().endswith(NESTED_ZIP_EXT) and info.file_size < (512 << 20):
            data = zf.read(info)
            if zipfile.is_zipfile(io.BytesIO(data)):
                with zipfile.ZipFile(io.BytesIO(data)) as inner:
                    scan_zip(inner, source, name + "!/", emit, counts)
            scan_stream(io.BytesIO(data).read, lambda r, n=name: emit(source, n, r))
            continue
        with zf.open(info) as f:
            scan_stream(f.read, lambda r, n=name: emit(source, n, r))


def scan_input(path, emit, counts):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            scan_zip(zf, path, "", emit, counts)
    else:
        counts["entries"] += 1
        counts["bytes"] += os.path.getsize(path)
        with open(path, "rb") as f:
            scan_stream(f.read, lambda r: emit(path, "", r))


def shown(text):
    text = text.replace("\t", "\\t").replace("\n", "\\n")
    return text if len(text) <= MAX_SHOWN else text[:MAX_SHOWN] + f"... [{len(text)} chars]"


def term_file(term):
    return "unique_" + term.replace(".", "dot_") + ".txt"


def write_reports(out_dir, inputs, records, counts):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "hits.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("source\tentry\toffset\tencoding\tterms\tstring\n")
        for r in records:
            f.write(f"{r['source']}\t{r['entry']}\t0x{r['offset']:x}\t{r['enc']}\t"
                    f"{','.join(r['terms'])}\t{shown(r['text'])}\n")

    with open(os.path.join(out_dir, "hits_context.txt"), "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(f"== {r['source']} :: {r['entry'] or '(file)'} @0x{r['offset']:x} "
                    f"[{r['enc']}] terms={','.join(r['terms'])}\n")
            for s in r["before"]:
                f.write(f"   {shown(s)}\n")
            f.write(f">> {shown(r['text'])}\n")
            for s in r["after"]:
                f.write(f"   {shown(s)}\n")
            f.write("\n")

    by_term = {t: collections.Counter() for t in TERMS}
    where = collections.defaultdict(collections.Counter)
    for r in records:
        for t in r["terms"]:
            by_term[t][r["text"]] += 1
            where[(r["source"], r["entry"])][t] += 1
    for t, counter in by_term.items():
        with open(os.path.join(out_dir, term_file(t)), "w", encoding="utf-8", newline="\n") as f:
            for text, n in counter.most_common():
                f.write(f"{n}\t{shown(text)}\n")

    lines = ["# String scan summary", "",
             f"Inputs: {', '.join(inputs)}  ",
             f"Scanned {counts['entries']} files/entries, {counts['bytes']:,} bytes. "
             f"Terms (case-insensitive): {', '.join(TERMS)}. Minimum string length {MIN_CHARS}.",
             "", "| term | hits | unique strings | hits in media entries |", "|---|---|---|---|"]
    for t in TERMS:
        media = sum(c[t] for (src, ent), c in where.items() if ent.lower().endswith(MEDIA_EXT))
        lines.append(f"| `{t}` | {sum(by_term[t].values())} | {len(by_term[t])} | {media} |")
    lines += ["", "## Hits per file / entry", "", "| file :: entry | " + " | ".join(TERMS) + " |",
              "|---|" + "---|" * len(TERMS)]
    for (src, ent), c in sorted(where.items()):
        lines.append(f"| {src} :: {ent or '(file)'} | " + " | ".join(str(c[t]) for t in TERMS) + " |")
    for t in TERMS:
        lines += ["", f"## Unique strings containing `{t}` (top 60 by count; all in {term_file(t)})", ""]
        for text, n in by_term[t].most_common(60):
            lines.append(f"- {n}× `{shown(text).replace('`', chr(39))}`")
    with open(os.path.join(out_dir, "SUMMARY.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return by_term, where


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    out_dir, inputs = argv[0], argv[1:]
    records, counts = [], collections.Counter()

    def emit(source, entry, rec):
        rec.update(source=source, entry=entry)
        records.append(rec)

    for path in inputs:
        scan_input(path, emit, counts)
    records.sort(key=lambda r: (r["source"], r["entry"], r["offset"], r["enc"]))
    by_term, where = write_reports(out_dir, inputs, records, counts)

    print(f"scanned {counts['entries']} files/entries, {counts['bytes']:,} bytes; {len(records)} hit strings")
    for t in TERMS:
        print(f"  {t!r:16} hits={sum(by_term[t].values()):6}  unique={len(by_term[t])}")
    print("hits per entry (" + ", ".join(TERMS) + "):")
    for (src, ent), c in sorted(where.items()):
        print(f"  {ent or src}: " + " ".join(str(c[t]) for t in TERMS))


if __name__ == "__main__":
    main(sys.argv[1:])
