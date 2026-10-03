"""Scaling checks: 100k-element reorders must stay near O(n log n).

Runs diff on a fixed-seed full shuffle and on a nearly-ordered reorder at
two scales (10k and 100k), then compares wall time and peak memory.  A
quadratic implementation (repeated linear scans or list splicing) blows
the 10x-size ratios far past the asserted bounds.
"""

import random
import time
import tracemalloc
import unittest

from forgekit import apply, diff

SMALL = 10_000
LARGE = 100_000
SEED = 26100421


def make_doc(ids):
    return {"items": [{"id": element_id, "v": i} for i, element_id in enumerate(ids)]}


def shuffled_ids(n, seed):
    ids = [f"e{i}" for i in range(n)]
    random.Random(seed).shuffle(ids)
    return ids


def nearly_ordered_ids(n, seed):
    """Sorted order with ~1% of elements relocated: few moves needed."""
    ids = [f"e{i}" for i in range(n)]
    rng = random.Random(seed)
    moved = []
    for _ in range(max(1, n // 100)):
        moved.append(ids.pop(rng.randrange(len(ids))))
    rng.shuffle(moved)
    return ids + moved


def measure(before, after):
    tracemalloc.start()
    start = time.perf_counter()
    patch = diff(before, after)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return patch, elapsed, peak


class TestScaling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {}

    def run_case(self, label, id_fn):
        for n in (SMALL, LARGE):
            before = make_doc([f"e{i}" for i in range(n)])
            after = make_doc(id_fn(n, SEED))
            patch, elapsed, peak = measure(before, after)
            moves = sum(op["op"] == "move" for op in patch)
            self.results[(label, n)] = (elapsed, peak, moves)
            print(f"\n[{label}] n={n}: diff={elapsed:.3f}s "
                  f"peak={peak / 1e6:.1f}MB moves={moves}", flush=True)
            # The patch must actually transform before into after.
            self.assertEqual(apply(before, patch), after)
        small = self.results[(label, SMALL)]
        large = self.results[(label, LARGE)]
        ratio_t = large[0] / max(small[0], 1e-9)
        ratio_m = large[1] / max(small[1], 1)
        print(f"[{label}] 10x size scaling: time x{ratio_t:.1f}, "
              f"memory x{ratio_m:.1f}", flush=True)
        # O(n log n) predicts ~12.5x time for 10x size; O(n^2) would be
        # ~100x.  Bounds are generous to stay robust on slow machines.
        self.assertLess(ratio_t, 60, f"{label}: time scaling looks quadratic")
        self.assertLess(ratio_m, 40, f"{label}: memory scaling looks super-linear")

    def test_random_shuffle(self):
        self.run_case("shuffle", shuffled_ids)

    def test_nearly_ordered(self):
        self.run_case("nearly-ordered", nearly_ordered_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
