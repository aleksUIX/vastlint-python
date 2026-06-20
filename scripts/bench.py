import glob
import os
import statistics
import sys
import time

import vastlint

SCRATCH = sys.argv[1] if len(sys.argv) > 1 else "../vastlint/scratch"
N_PER_BUCKET = int(os.environ.get("N", "200"))
REPEATS = int(os.environ.get("REPEATS", "5"))

BUCKETS = [
    ("small ~7KB", "heavy-corpus-small"),
    ("17KB", "heavy-corpus-17k"),
    ("medium ~23KB", "heavy-corpus-medium"),
    ("44KB", "heavy-corpus-44k"),
    ("large ~347KB", "heavy-corpus-large"),
]


def load(bucket_dir):
    paths = sorted(glob.glob(os.path.join(SCRATCH, bucket_dir, "*.xml")))[:N_PER_BUCKET]
    tags = []
    for p in paths:
        with open(p, "rb") as f:
            tags.append(f.read())
    return tags


def bench(tags):
    # warmup
    for t in tags[: min(20, len(tags))]:
        vastlint.validate(t)

    per_tag_us = []
    wall = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        for t in tags:
            vastlint.validate(t)
        dt = time.perf_counter() - t0
        wall.append(dt)
        per_tag_us.append((dt / len(tags)) * 1e6)

    # per-tag latency distribution (single-run, finer grained)
    lat = []
    for t in tags:
        s = time.perf_counter()
        vastlint.validate(t)
        lat.append((time.perf_counter() - s) * 1e6)
    lat.sort()
    return {
        "n": len(tags),
        "mean_us": statistics.mean(per_tag_us),
        "p50_us": lat[len(lat) // 2],
        "p95_us": lat[int(len(lat) * 0.95)],
        "p99_us": lat[int(len(lat) * 0.99)],
        "tags_per_sec": len(tags) / statistics.mean(wall),
    }


print(f"vastlint {vastlint.version()}  python {sys.version.split()[0]}")
print(f"N={N_PER_BUCKET} per bucket, REPEATS={REPEATS}\n")
hdr = f"{'bucket':<16}{'n':>5}{'mean us':>10}{'p50 us':>9}{'p95 us':>9}{'p99 us':>9}{'tags/sec':>12}"
print(hdr)
print("-" * len(hdr))
for label, d in BUCKETS:
    tags = load(d)
    if not tags:
        print(f"{label:<16}  (no files)")
        continue
    r = bench(tags)
    print(
        f"{label:<16}{r['n']:>5}{r['mean_us']:>10.1f}{r['p50_us']:>9.1f}"
        f"{r['p95_us']:>9.1f}{r['p99_us']:>9.1f}{r['tags_per_sec']:>12,.0f}"
    )
