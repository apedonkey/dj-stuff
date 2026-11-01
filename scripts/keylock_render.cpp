// keylock_render.cpp: plays a file through key lock (Signalsmith Stretch) the way a deck would, block by block,
// and saves the result for listening tests. Input and output are raw interleaved stereo float32 (ffmpeg -f f32le).
//
//   keylock_render in.f32 out.f32 [--rate 48000] [--ratio 1.08] [--preset default|cheaper|custom]
//                  [--win ms] [--hop ms] [--split 0|1] [--block 256]
//
// The output is trimmed by the stretcher's latency so it starts where the input starts, and is input / ratio long.
// Built for Windows by scripts/keylock_listen.sh (MSVC); the same code builds for the Quest.
#include "signalsmith-stretch.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: keylock_render in.f32 out.f32 [--ratio 1.08] [--preset default|cheaper|custom] ...\n");
        return 2;
    }
    int rate = 48000, block = 256, split = -1;
    double ratio = 1.08, winMs = 120, hopMs = 30;
    std::string preset = "default";
    for (int i = 3; i + 1 < argc; i += 2) {
        std::string k = argv[i], v = argv[i + 1];
        if (k == "--rate") rate = atoi(v.c_str());
        else if (k == "--ratio") ratio = atof(v.c_str());
        else if (k == "--preset") preset = v;
        else if (k == "--win") winMs = atof(v.c_str());
        else if (k == "--hop") hopMs = atof(v.c_str());
        else if (k == "--split") split = atoi(v.c_str());
        else if (k == "--block") block = atoi(v.c_str());
        else { fprintf(stderr, "unknown option %s\n", k.c_str()); return 2; }
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }
    fseek(f, 0, SEEK_END);
    const long frames = ftell(f) / long(2 * sizeof(float));
    fseek(f, 0, SEEK_SET);
    std::vector<float> inter(size_t(frames) * 2);
    if (fread(inter.data(), sizeof(float), inter.size(), f) != inter.size()) { fprintf(stderr, "short read\n"); return 1; }
    fclose(f);
    std::vector<std::vector<float>> in(2, std::vector<float>(frames));
    for (long i = 0; i < frames; ++i) {
        in[0][i] = inter[size_t(i) * 2];
        in[1][i] = inter[size_t(i) * 2 + 1];
    }

    signalsmith::stretch::SignalsmithStretch<float> s(1234);
    if (preset == "cheaper") s.presetCheaper(2, float(rate), split != 0);
    else if (preset == "custom") s.configure(2, int(rate * winMs / 1000), int(rate * hopMs / 1000), split == 1);
    else s.presetDefault(2, float(rate), split == 1);

    // Input sample 0 comes out after the output latency plus the input latency (in output samples).
    const long trim = s.outputLatency() + std::lround(s.inputLatency() / ratio);
    const long outFrames = long(frames / ratio);
    const int maxIn = int(std::ceil(block * ratio)) + 2;
    std::vector<float> ib0(maxIn), ib1(maxIn), ob0(block), ob1(block), out;
    out.reserve(size_t(outFrames) * 2);
    long pos = 0, produced = 0;
    double carry = 0;
    while (produced < trim + outFrames) {
        carry += block * ratio;
        const int inN = int(carry);
        carry -= inN;
        for (int i = 0; i < inN; ++i) {
            const long p = pos + i;
            ib0[i] = p < frames ? in[0][p] : 0.f;
            ib1[i] = p < frames ? in[1][p] : 0.f;
        }
        pos += inN;
        float *ip[2] = {ib0.data(), ib1.data()};
        float *op[2] = {ob0.data(), ob1.data()};
        s.process(ip, inN, op, block);
        for (int i = 0; i < block; ++i, ++produced) {
            if (produced >= trim && produced < trim + outFrames) {
                out.push_back(ob0[i]);
                out.push_back(ob1[i]);
            }
        }
    }

    FILE *o = fopen(argv[2], "wb");
    if (!o || fwrite(out.data(), sizeof(float), out.size(), o) != out.size()) { fprintf(stderr, "cannot write\n"); return 1; }
    fclose(o);
    printf("%s: %.2f s -> %.2f s, ratio %.2f, window %.0f ms, hop %.0f ms, delay %.0f ms, trimmed %ld samples\n", argv[2],
           double(frames) / rate, double(outFrames) / rate, ratio, 1000.0 * s.blockSamples() / rate,
           1000.0 * s.intervalSamples() / rate, 1000.0 * s.outputLatency() / rate, trim);
    return 0;
}
