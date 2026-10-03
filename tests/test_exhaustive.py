"""Exhaustive small-scale reorder checks (<= 7 elements).

For every permutation of every size up to 7 we verify:
  * apply(before, diff(before, after)) == after   (replay succeeds)
  * the number of move ops equals n - LIS(after)  (provably minimal)
  * the patch is deterministic
"""

import itertools
import unittest

from forgekit import apply, diff


def lis_length_brute(order):
    """Independent O(n^2) DP LIS length used as the oracle."""
    best = 0
    n = len(order)
    dp = [1] * n
    for i in range(n):
        for j in range(i):
            if order[j] < order[i]:
                dp[i] = max(dp[i], dp[j] + 1)
        best = max(best, dp[i])
    return best if n else 0


def make_doc(ids):
    return {"items": [{"id": element_id, "v": element_id} for element_id in ids]}


class TestExhaustiveReorders(unittest.TestCase):
    def check_case(self, ids, perm):
        before = make_doc(ids)
        after = make_doc([ids[i] for i in perm])
        before_snapshot = make_doc(ids)
        patch = diff(before, after)
        self.assertEqual(patch, diff(before, after), "diff must be deterministic")
        # Replay step by step: every intermediate prefix must apply cleanly.
        doc = before
        for op in patch:
            doc = apply(doc, [op])
        self.assertEqual(doc, after)
        # Inputs must be untouched.
        self.assertEqual(before, before_snapshot)
        # Minimal move count: survivors (= all ids) minus LIS length.
        moves = [op for op in patch if op["op"] == "move"]
        rank = {element_id: i for i, element_id in enumerate(ids)}
        sequence = [rank[ids[i]] for i in perm]
        expected = len(ids) - lis_length_brute(sequence)
        self.assertEqual(len(moves), expected,
                         f"{ids} -> {perm}: {len(moves)} moves, expected {expected}")
        # No surviving id may be removed/recreated or wholesale replaced.
        for op in patch:
            self.assertNotEqual(op["op"], "remove")
            if op["op"] in ("add", "replace"):
                self.assertGreater(op["path"].count("/"), 2)

    def test_all_permutations_up_to_7(self):
        for n in range(0, 8):
            ids = [f"e{i}" for i in range(n)]
            for perm in itertools.permutations(range(n)):
                self.check_case(ids, perm)

    def test_first_to_last_is_single_move(self):
        # Moving the head to the tail needs exactly one move, while a naive
        # left-to-right aligner would emit n-1 moves.
        ids = ["a", "b", "c", "d", "e"]
        before = make_doc(ids)
        after = make_doc(ids[1:] + ids[:1])
        patch = diff(before, after)
        moves = [op for op in patch if op["op"] == "move"]
        self.assertEqual(len(moves), 1)
        self.assertEqual(apply(before, patch), after)

    def test_reverse_order(self):
        n = 7
        ids = [f"e{i}" for i in range(n)]
        before = make_doc(ids)
        after = make_doc(ids[::-1])
        patch = diff(before, after)
        moves = [op for op in patch if op["op"] == "move"]
        self.assertEqual(len(moves), n - 1)  # LIS of a reversal has length 1
        self.assertEqual(apply(before, patch), after)


if __name__ == "__main__":
    unittest.main()
