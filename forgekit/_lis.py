"""Longest increasing subsequence (O(n log n), deterministic)."""

from bisect import bisect_left
from typing import List, Sequence


def lis_membership(seq: Sequence[int]) -> List[bool]:
    """Return a boolean mask marking one longest increasing subsequence.

    Uses patience sorting with parent pointers.  The chosen subsequence is
    deterministic: identical inputs always yield the identical mask.
    """
    n = len(seq)
    tails: List[int] = []  # tails[k] = index of smallest tail of an IS of length k+1
    parent = [-1] * n
    for i, value in enumerate(seq):
        pos = bisect_left(tails, value, key=lambda j: seq[j])
        if pos == len(tails):
            tails.append(i)
        else:
            tails[pos] = i
        if pos > 0:
            parent[i] = tails[pos - 1]
    mask = [False] * n
    if tails:
        node = tails[-1]
        while node != -1:
            mask[node] = True
            node = parent[node]
    return mask
