"""Scaling checks for diff() on a single large array.

Runs a fixed-seed full shuffle and a near-sorted reordering at n=100_000
and n=10_000, and compares wall time and peak memory.  An implementation
with repeated linear scans or list splicing grows quadratically and blows
the (generous) ratio budgets below; the treap-based O(n log n) differ does
not come close to them.
"""

import random
import time
import tracemalloc
import unittest

from forgekit import apply, diff

SMALL = 10_000
LARGE = 100_000
SEED = 20261004

# n log n predicts ~13x time and exactly 10x memory for a 10x size bump.
# Quadratic implementations land near 100x time; budgets sit in between.
MAX_TIME_RATIO = 40.0
MAX_MEMORY_RATIO = 30.0


def make_doc(ids):
    return {"arr": [{"id": i, "v": 0} for i in ids]}


def shuffled_ids(n):
    ids = [f"e{i:06d}" for i in range(n)]
    random.Random(SEED).shuffle(ids)
    return ids


def near_sorted_ids(n):
    ids = [f"e{i:06d}" for i in range(n)]
    rng = random.Random(SEED)
    for _ in range(max(1, n // 50)):
        i = rng.randrange(n)
        j = rng.randrange(n)
        ids.insert(j, ids.pop(i))
    return ids


def measure(before, after):
    tracemalloc.start()
    start = time.perf_counter()
    patch = diff(before, after)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return patch, elapsed, peak


class PerfTest(unittest.TestCase):
    def check_scaling(self, label, make_ids):
        results = {}
        for n in (SMALL, LARGE):
            ids = make_ids(n)
            before = make_doc(sorted(ids))
            after = make_doc(ids)
            patch, elapsed, peak = measure(before, after)
            moves = sum(1 for op in patch if op["op"] == "move")
            results[n] = (elapsed, peak, moves, patch, before, after)
            print(f"\n[{label}] n={n}: diff={elapsed:.3f}s "
                  f"peak={peak / 1e6:.1f}MB moves={moves}", flush=True)

        t_small, m_small = results[SMALL][0], results[SMALL][1]
        t_large, m_large = results[LARGE][0], results[LARGE][1]
        time_ratio = t_large / max(t_small, 1e-9)
        mem_ratio = m_large / max(m_small, 1)
        print(f"[{label}] time ratio={time_ratio:.1f}x mem ratio={mem_ratio:.1f}x",
              flush=True)
        self.assertLess(time_ratio, MAX_TIME_RATIO,
                        f"{label}: time grew {time_ratio:.1f}x for 10x input "
                        "(quadratic would be ~100x)")
        self.assertLess(mem_ratio, MAX_MEMORY_RATIO,
                        f"{label}: memory grew {mem_ratio:.1f}x for 10x input")

        # correctness at the large scale: replay must reproduce the target
        _, _, _, patch, before, after = results[LARGE]
        self.assertEqual(apply(before, patch), after)

    def test_full_shuffle_scaling(self):
        self.check_scaling("shuffle", shuffled_ids)

    def test_near_sorted_scaling(self):
        self.check_scaling("near-sorted", near_sorted_ids)


if __name__ == "__main__":
    unittest.main()
