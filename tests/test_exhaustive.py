"""Exhaustive permutation check for n <= 7.

For every permutation of n elements: the patch must replay to the target
and use exactly n - LIS moves (the provable minimum for element moves).
"""

import itertools
import unittest

from forgekit import apply, diff


def make_doc(order):
    return {"arr": [{"id": str(i)} for i in order]}


def lis_length(seq):
    """Independent O(n^2) DP, used as the reference for minimality."""
    if not seq:
        return 0
    best = [1] * len(seq)
    for i in range(len(seq)):
        for j in range(i):
            if seq[j] < seq[i]:
                best[i] = max(best[i], best[j] + 1)
    return max(best)


def expected_min_moves(source_order, target_order):
    target_pos = {element_id: i for i, element_id in enumerate(target_order)}
    mapped = [target_pos[element_id] for element_id in source_order]
    return len(source_order) - lis_length(mapped)


class ExhaustivePermutationTest(unittest.TestCase):
    def check_all_permutations(self, n):
        ids = [str(i) for i in range(n)]
        for perm in itertools.permutations(ids):
            before = make_doc(ids)
            after = make_doc(list(perm))
            patch = diff(before, after)
            result = apply(before, patch)
            self.assertEqual(result, after, f"n={n} perm={perm}")
            moves = sum(1 for op in patch if op["op"] == "move")
            self.assertEqual(
                moves,
                expected_min_moves(ids, list(perm)),
                f"non-minimal moves for n={n} perm={perm}",
            )
            # no other op kinds are needed for a pure permutation
            self.assertTrue(all(op["op"] == "move" for op in patch))

    def test_permutations_up_to_4(self):
        for n in range(0, 5):
            self.check_all_permutations(n)

    def test_permutations_5(self):
        self.check_all_permutations(5)

    def test_permutations_6(self):
        self.check_all_permutations(6)

    def test_permutations_7(self):
        self.check_all_permutations(7)

    def test_first_to_last_is_a_single_move(self):
        # Rotating the first element to the end needs exactly one move,
        # while a naive left-to-right alignment would move n-1 elements.
        n = 7
        ids = [str(i) for i in range(n)]
        rotated = ids[1:] + ids[:1]
        patch = diff(make_doc(ids), make_doc(rotated))
        moves = [op for op in patch if op["op"] == "move"]
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["from"], "/arr/0")
        self.assertEqual(moves[0]["path"], f"/arr/{n - 1}")
        self.assertEqual(apply(make_doc(ids), patch), make_doc(rotated))

    def test_last_to_first_is_a_single_move(self):
        n = 7
        ids = [str(i) for i in range(n)]
        rotated = ids[-1:] + ids[:-1]
        patch = diff(make_doc(ids), make_doc(rotated))
        moves = [op for op in patch if op["op"] == "move"]
        self.assertEqual(len(moves), 1)
        self.assertEqual(apply(make_doc(ids), patch), make_doc(rotated))

    def test_full_reversal(self):
        n = 7
        ids = [str(i) for i in range(n)]
        patch = diff(make_doc(ids), make_doc(ids[::-1]))
        moves = sum(1 for op in patch if op["op"] == "move")
        self.assertEqual(moves, n - 1)  # LIS of a reversal has length 1
        self.assertEqual(apply(make_doc(ids), patch), make_doc(ids[::-1]))


if __name__ == "__main__":
    unittest.main()
