"""Copy the finished loops into deliver/Loops with friendly names and write deliver/README.txt (system Python 3).

  python deliver.py [--skip-gate] [FILTER ...]

The pack runs at 140 BPM half-time; the 128 BPM cuts made before the switch ship as extras. Every
renders/<concept>/<concept>_<variant>_<bpm>bpm_8bars_1080p30.mp4 (140, and 128 for the extras) is gated again with its
own grid (check_loop.py --video; 128 is straight 4-on-the-floor) unless --skip-gate; loops that fail are listed and not
copied. FILTER substrings (e.g. giant_halo, stomp_lava) limit which renders are copied this run; the README always lists
everything in deliver/Loops. Names: "Dino - Fossil Scan (cyan) 140bpm.mp4".
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_set import CONCEPTS, INTRO_BARS, ROOT, catalog  # noqa: E402

TEMPOS = {140: ["--bpm", "140", "--halftime"], 128: ["--bpm", "128", "--straight"]}
SLOTS = {"giant_halo": "giant intro", "fossil_scan": "intro", "amber_dna": "intro / breakdown",
         "spine_tunnel": "build into drop", "raptor_run": "build", "extinction_event": "drop",
         "stomp": "drop (heavy / half-time)", "primeval_jungle": "breakdown", "lava_moon": "outro / breakdown",
         "sting": "act changes / ID"}
ORDER = list(SLOTS)
ABOUT = {
    "giant_halo": "For the giant intro (lift up, one spotlight): a huge red halo like a backlit eclipse on black, "
                  "soft drifting smoke, a slow breath on the kick and snare. Calm, no hits.",
    "fossil_scan": "The stage's T. rex skull as a laser-scanned hologram; a scan plane sweeps down once per bar.",
    "amber_dna": "A double helix of amber beads; a step sequencer lights one rung per accent, a spark lands on "
                 "each downbeat.",
    "spine_tunnel": "A fly-through of an endless neon ribcage toward a lava moon; lasers in bars 5-8, a ghost arch "
                    "and palette swell into each 4-bar hit.",
    "raptor_run": "A pack of neon raptor silhouettes sprinting along a glowing horizon; on bar 5 the lead raptor "
                  "leaps and the laser fans burst open.",
    "extinction_event": "A meteor streaks in over bars 6-8 and hits the jungle horizon on the loop's downbeat: "
                        "flare, shockwave, burning skyline, embers.",
    "stomp": "Giant three-toed footprints slam down toward the camera with shakes, dust rings and racing cracks.",
    "primeval_jungle": "Layered jungle silhouettes in slow parallax, a sauropod behind the trees, a laser sheet "
                       "slicing the canopy once per bar.",
    "lava_moon": "The Dino Stage in silhouette against a huge churning lava moon with a chasing bulb ring and "
                 "swinging uplights.",
    "sting": "DINO STAGE in neon bones: assembles on the downbeat, pulses, breaks apart and flies back in.",
}
NAME_RE = re.compile(r"Dino - (.+) \((\w+)\) (\d+)bpm\.mp4")


def concept_of(display):
    return next((c for c, (d, _) in CONCEPTS.items() if d == display), None)


def intro_of_set():
    """(bars, 'm:ss') of Giant Halo's opening in the delivered Full Set, read from its timeline (what was encoded)."""
    path = os.path.join(ROOT, "deliver", "Dino Visuals - Full Set - timeline.txt")
    bars = INTRO_BARS
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            m = re.match(r"\S+\s+\S+\s+(\d+) bars\s+Giant Halo", fh.readline())
        bars = int(m.group(1)) if m else bars
    secs = round(bars * 240 / 140)
    return bars, f"{secs // 60}:{secs % 60:02d}"


def write_readme(out_dir):
    """deliver/README.txt from what is in deliver/Loops (140 BPM loops first, then the 128 BPM extras)."""
    rows = []
    for path in glob.glob(os.path.join(out_dir, "Dino - *.mp4")):
        m = NAME_RE.fullmatch(os.path.basename(path))
        if m and concept_of(m.group(1)):
            rows.append((int(m.group(3)), concept_of(m.group(1)), m.group(2), os.path.basename(path)))
    rows.sort(key=lambda r: (-r[0], ORDER.index(r[1]), r[2]))
    main = [r for r in rows if r[0] == 140]
    extra = [r for r in rows if r[0] != 140]
    with open(os.path.join(ROOT, "deliver", "README.txt"), "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("DINO VISUALS - original VJ loops for the Dino Stage (Tribe XR)\n"
                 "All shapes, motion and light are generated from our own Blender scripts: no downloaded footage, "
                 "images, models or fonts.\n\n"
                 "Every loop: 8 bars, seamless, 1920x1080 30 fps, H.264, no audio.\n"
                 "  140 BPM half-time (the pack): 8 bars = 13.7 s (411 frames). Accents on the kick (beat 1) and the "
                 "snare (beat 3), no 4-on-the-floor pulse.\n"
                 "  128 BPM extras: 15.0 s (450 frames), 4-on-the-floor, made before the pack moved to 140.\n"
                 "Start a loop on a phrase (bar 1 of 8, 16 or 32) and its accents and swells land with the music.\n"
                 "Built for a dark night show: no strobing (at most 3 flashes per second, no one-frame hits), "
                 "nothing larger than about 1 m2 of the wall brighter than 65%, no full-frame white.\n\n")
        bars, length = intro_of_set()
        fh.write(f"Dino Visuals - Full Set.mp4: one continuous 60:00 video at 140 BPM. It opens with Giant Halo ({bars} "
                 f"bars, {length}) for the giant\nintro, then six acts of about 10 minutes (intro, build, peak, "
                 "breakdown, peak, outro), each opening with the sting,\nand closes on Lava Moon. 2-bar crossfades on "
                 "the phrase; every loop is used, none repeats within 10 minutes.\nStart it on the first downbeat of "
                 "the set. Its timeline is in 'Dino Visuals - Full Set - timeline.txt'.\n\n")
        for title, group in ((f"LOOPS AT 140 BPM HALF-TIME ({len(main)})", main),
                             (f"EXTRAS AT 128 BPM ({len(extra)})", extra)):
            if not group:
                continue
            fh.write(title + "\n")
            last = None
            for _, concept, variant, name in group:
                if concept != last:
                    fh.write(f"\n  {CONCEPTS[concept][0]} - {SLOTS[concept]}\n    {ABOUT[concept]}\n")
                    last = concept
                fh.write(f"    {name}\n")
            fh.write("\n")
    return len(main), len(extra)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-gate", action="store_true")
    ap.add_argument("filters", nargs="*")
    a = ap.parse_args()
    out_dir = os.path.join(ROOT, "deliver", "Loops")
    os.makedirs(out_dir, exist_ok=True)
    failed = []
    for bpm, grid in TEMPOS.items():
        loops = sorted(catalog(bpm), key=lambda lp: (ORDER.index(lp.concept), lp.variant))
        for lp in loops:
            if a.filters and not any(s in os.path.basename(lp.path) for s in a.filters):
                continue
            if not a.skip_gate:
                r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_loop.py"), "--video", lp.path]
                                   + grid, capture_output=True, text=True)
                if r.returncode != 0:
                    failed.append(f"{lp.name} {bpm}: {r.stdout.strip().splitlines()[-1]}")
                    continue
            name = f"Dino - {lp.name} {bpm}bpm.mp4"
            shutil.copyfile(lp.path, os.path.join(out_dir, name))
            print(f"delivered {name}")
    n_main, n_extra = write_readme(out_dir)
    if failed:
        print("NOT delivered (gate failed):\n  " + "\n  ".join(failed))
    print(f"deliver/Loops: {n_main} loops at 140 BPM + {n_extra} extras at 128 BPM; README.txt written")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
