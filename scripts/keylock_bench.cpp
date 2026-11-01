// keylock_bench.cpp: how much CPU key lock (Signalsmith Stretch) takes on the Quest.
//
// Runs N stereo decks through the stretcher the way an audio callback would: every output block (256 frames at
// 48 kHz = 5.33 ms) each deck consumes block x ratio input frames and produces one block. Every block is timed, so
// the result shows the average load and the worst blocks (the ones that would glitch). Input is a synthetic
// 140 BPM loop (sub wobble, kick, hats, chord); the stretcher's cost doesn't depend much on the content.
//
// Build: scripts/keylock_bench.sh (Android NDK r26d, aarch64). One run = one summary line.
//   keylock_bench [--decks 4] [--rate 48000] [--block 256] [--seconds 30] [--ratio 1.08]
//                 [--preset default|cheaper|custom] [--win ms] [--hop ms] [--split 0|1] [--cpu N]
#include "signalsmith-stretch.h"

#include <sched.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>

namespace {

double now(clockid_t clock) {
    timespec t;
    clock_gettime(clock, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}

long readLong(const std::string &path) {
    FILE *f = fopen(path.c_str(), "r");
    if (!f) return -1;
    long v = -1;
    if (fscanf(f, "%ld", &v) != 1) v = -1;
    fclose(f);
    return v;
}

struct Args {
    int decks = 4, rate = 48000, block = 256, cpu = -1, split = -1;
    double seconds = 30, ratio = 1.08, winMs = 120, hopMs = 30;
    std::string preset = "default";
};

Args parse(int argc, char **argv) {
    Args a;
    for (int i = 1; i + 1 < argc; i += 2) {
        std::string k = argv[i], v = argv[i + 1];
        if (k == "--decks") a.decks = atoi(v.c_str());
        else if (k == "--rate") a.rate = atoi(v.c_str());
        else if (k == "--block") a.block = atoi(v.c_str());
        else if (k == "--seconds") a.seconds = atof(v.c_str());
        else if (k == "--ratio") a.ratio = atof(v.c_str());
        else if (k == "--preset") a.preset = v;
        else if (k == "--win") a.winMs = atof(v.c_str());
        else if (k == "--hop") a.hopMs = atof(v.c_str());
        else if (k == "--split") a.split = atoi(v.c_str());
        else if (k == "--cpu") a.cpu = atoi(v.c_str());
        else { fprintf(stderr, "unknown option %s\n", k.c_str()); exit(2); }
    }
    return a;
}

// A 16-second stereo loop at 140 BPM: half-time wobble on a 55 Hz sub, a kick every beat, noise hats every
// half beat, and a quiet minor chord. Left and right differ slightly so the stretcher sees real stereo.
std::vector<std::vector<float>> makeLoop(int rate) {
    const int frames = rate * 16;
    std::vector<std::vector<float>> ch(2, std::vector<float>(frames));
    std::mt19937 rng(140);
    std::uniform_real_distribution<float> noise(-1.f, 1.f);
    const double beat = 60.0 / 140.0, pi2 = 2 * M_PI;
    for (int i = 0; i < frames; ++i) {
        double t = double(i) / rate;
        double inBeat = std::fmod(t, beat), inHalf = std::fmod(t, beat / 2);
        double wobble = 0.5 + 0.5 * std::sin(pi2 * t / (beat * 2));
        double sub = 0.35 * wobble * std::sin(pi2 * 55 * t);
        double kick = 0.6 * std::exp(-inBeat * 18) * std::sin(pi2 * (45 + 120 * std::exp(-inBeat * 30)) * t);
        double hat = 0.12 * std::exp(-inHalf * 60);
        double chord = 0.05 * (std::sin(pi2 * 220 * t) + std::sin(pi2 * 261.63 * t) + std::sin(pi2 * 329.63 * t));
        float n = noise(rng);
        ch[0][i] = float(sub + kick + hat * n + chord);
        ch[1][i] = float(sub + kick + hat * noise(rng) + chord * 0.9);
    }
    return ch;
}

}  // namespace

int main(int argc, char **argv) {
    Args a = parse(argc, argv);

    if (a.cpu >= 0) {
        cpu_set_t set;
        CPU_ZERO(&set);
        CPU_SET(a.cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0) {
            printf("cpu=%d could not pin (offline or not allowed)\n", a.cpu);
            return 1;
        }
    }

    auto loop = makeLoop(a.rate);
    const long loopFrames = long(loop[0].size());

    std::vector<signalsmith::stretch::SignalsmithStretch<float>> decks;
    decks.reserve(a.decks);
    for (int d = 0; d < a.decks; ++d) {
        decks.emplace_back(1000 + d);
        auto &s = decks.back();
        if (a.preset == "cheaper") s.presetCheaper(2, float(a.rate), a.split != 0);  // library default: split on
        else if (a.preset == "custom")
            s.configure(2, int(a.rate * a.winMs / 1000), int(a.rate * a.hopMs / 1000), a.split == 1);
        else s.presetDefault(2, float(a.rate), a.split == 1);  // library default: split off
    }
    const int winSamples = decks[0].blockSamples(), hopSamples = decks[0].intervalSamples();
    const double inLatMs = 1000.0 * decks[0].inputLatency() / a.rate;
    const double outLatMs = 1000.0 * decks[0].outputLatency() / a.rate;

    // Per-deck scratch buffers, sized for the largest input block, so the timed loop never allocates.
    const int maxIn = int(std::ceil(a.block * a.ratio)) + 2;
    std::vector<std::vector<float>> inBuf(a.decks * 2, std::vector<float>(maxIn));
    std::vector<std::vector<float>> outBuf(a.decks * 2, std::vector<float>(a.block));
    std::vector<long> readPos(a.decks);
    std::vector<double> carry(a.decks, 0.0);
    for (int d = 0; d < a.decks; ++d) readPos[d] = (loopFrames / a.decks) * d;  // decks start at different bars

    const long blocks = long(a.seconds * a.rate / a.block);
    std::vector<double> times(blocks);
    float sink = 0;  // keeps the optimiser from dropping the output

    // Warm-up: fill each stretcher's history so the timed part is steady state.
    auto runBlock = [&](int d) {
        carry[d] += a.block * a.ratio;
        int inN = int(carry[d]);
        carry[d] -= inN;
        float *in[2] = {inBuf[d * 2].data(), inBuf[d * 2 + 1].data()};
        float *out[2] = {outBuf[d * 2].data(), outBuf[d * 2 + 1].data()};
        for (int c = 0; c < 2; ++c)
            for (int i = 0; i < inN; ++i) in[c][i] = loop[c][(readPos[d] + i) % loopFrames];
        readPos[d] = (readPos[d] + inN) % loopFrames;
        decks[d].process(in, inN, out, a.block);
        sink += out[0][a.block / 2];
    };
    for (int w = 0; w < (a.rate / a.block); ++w)
        for (int d = 0; d < a.decks; ++d) runBlock(d);

    const double wall0 = now(CLOCK_MONOTONIC), cpu0 = now(CLOCK_THREAD_CPUTIME_ID);
    for (long b = 0; b < blocks; ++b) {
        double t0 = now(CLOCK_MONOTONIC);
        for (int d = 0; d < a.decks; ++d) runBlock(d);
        times[b] = now(CLOCK_MONOTONIC) - t0;
    }
    const double wall = now(CLOCK_MONOTONIC) - wall0, cpu = now(CLOCK_THREAD_CPUTIME_ID) - cpu0;

    const int onCpu = sched_getcpu();
    const long curKHz = readLong("/sys/devices/system/cpu/cpu" + std::to_string(onCpu) + "/cpufreq/scaling_cur_freq");
    const long maxKHz = readLong("/sys/devices/system/cpu/cpu" + std::to_string(onCpu) + "/cpufreq/cpuinfo_max_freq");

    std::vector<double> sorted(times);
    std::sort(sorted.begin(), sorted.end());
    const double period = double(a.block) / a.rate;
    auto pct = [&](double q) { return 100.0 * sorted[std::min<long>(blocks - 1, long(q * blocks))] / period; };
    double mean = 0;
    for (double t : times) mean += t;
    mean /= blocks;
    long over50 = 0, over100 = 0;
    for (double t : times) {
        if (t > period * 0.5) ++over50;
        if (t > period) ++over100;
    }

    printf("cpu=%d (%ld/%ld MHz) preset=%s win=%.0fms hop=%.0fms split=%d decks=%d ratio=%.2f | "
           "avg %.1f%% p99 %.1f%% p99.9 %.1f%% max %.1f%% of a %.2f ms block | blocks >50%%: %ld, >100%%: %ld of %ld | "
           "latency in %.0f ms + out %.0f ms | cpu/wall %.2f | all decks run x%.1f faster than real time%s\n",
           onCpu, curKHz / 1000, maxKHz / 1000, a.preset.c_str(), 1000.0 * winSamples / a.rate,
           1000.0 * hopSamples / a.rate, a.preset == "cheaper" ? (a.split != 0) : (a.split == 1), a.decks, a.ratio,
           100.0 * mean / period, pct(0.99), pct(0.999), 100.0 * sorted.back() / period, 1000.0 * period, over50,
           over100, blocks, inLatMs, outLatMs, cpu / wall, (blocks * period) / wall,
           std::isfinite(sink) ? "" : " (nan)");
    return 0;
}
