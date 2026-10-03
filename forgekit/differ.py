"""Compute an RFC 6902 patch turning ``before`` into ``after``.

Array elements are matched by their string ``id``; surviving ids are never
deleted/recreated, and reordering uses a minimal number of ``move`` ops
(n - LIS), computed in O(n log n) including live-index resolution.
"""

from copy import deepcopy
from typing import Any, Dict, List

from forgekit.pointer import build_pointer
from forgekit.treap import Treap

Json = Any
Op = Dict[str, Any]


def diff(before: Json, after: Json) -> List[Op]:
    """Return an RFC 6902 patch that transforms ``before`` into ``after``.

    Deterministic: equal inputs always produce the same patch.  Does not
    mutate either argument.
    """
    ops: List[Op] = []
    _diff_value(before, after, [], ops)
    return ops


def _leaf_equal(left: Json, right: Json) -> bool:
    # bool must not compare equal to int: ``type`` identity is checked first.
    return type(left) is type(right) and left == right


def _diff_value(before: Json, after: Json, tokens: List[str], ops: List[Op]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        _diff_object(before, after, tokens, ops)
    elif isinstance(before, list) and isinstance(after, list):
        _diff_array(before, after, tokens, ops)
    elif not _leaf_equal(before, after):
        ops.append({"op": "replace", "path": build_pointer(tokens), "value": deepcopy(after)})


def _diff_object(before: Dict[str, Json], after: Dict[str, Json], tokens: List[str], ops: List[Op]) -> None:
    for key, old_value in before.items():
        if key not in after:
            ops.append({"op": "remove", "path": build_pointer(tokens + [key])})
        else:
            _diff_value(old_value, after[key], tokens + [key], ops)
    for key, new_value in after.items():
        if key not in before:
            ops.append({"op": "add", "path": build_pointer(tokens + [key]), "value": deepcopy(new_value)})


def _diff_array(before: List[Json], after: List[Json], tokens: List[str], ops: List[Op]) -> None:
    _check_elements(before, tokens)
    _check_elements(after, tokens)
    before_ids = [element["id"] for element in before]
    after_ids = [element["id"] for element in after]
    after_index = {element_id: i for i, element_id in enumerate(after_ids)}
    before_id_set = set(before_ids)
    after_id_set = set(after_ids)

    # 1. Field changes of surviving ids, addressed by their before-index.
    for i, element in enumerate(before):
        element_id = before_ids[i]
        if element_id in after_id_set:
            _diff_value(element, after[after_index[element_id]], tokens + [str(i)], ops)

    # 2. Removals, highest index first so earlier indices stay valid.
    for i in range(len(before) - 1, -1, -1):
        if before_ids[i] not in after_id_set:
            ops.append({"op": "remove", "path": build_pointer(tokens + [str(i)])})

    # 3. Minimal moves on the surviving-only sequence.
    surviving_before = [element_id for element_id in before_ids if element_id in after_id_set]
    surviving_after = [element_id for element_id in after_ids if element_id in before_id_set]
    _emit_moves(surviving_before, surviving_after, tokens, ops)

    # 4. Insertions of new ids at their final index, ascending.
    for j, element in enumerate(after):
        if after_ids[j] not in before_id_set:
            ops.append({"op": "add", "path": build_pointer(tokens + [str(j)]), "value": deepcopy(element)})


def _check_elements(array: List[Json], tokens: List[str]) -> None:
    seen = set()
    for element in array:
        if not isinstance(element, dict) or not isinstance(element.get("id"), str):
            raise ValueError(
                f"array at {build_pointer(tokens) or '/'!r} must contain objects "
                "with a string 'id'"
            )
        element_id = element["id"]
        if element_id in seen:
            raise ValueError(f"duplicate id {element_id!r} in array at {build_pointer(tokens)!r}")
        seen.add(element_id)


def _emit_moves(surviving_before: List[str], surviving_after: List[str], tokens: List[str], ops: List[Op]) -> None:
    m = len(surviving_before)
    if m < 2:
        return
    target_pos = {element_id: i for i, element_id in enumerate(surviving_after)}
    keep = _lis_keep([target_pos[element_id] for element_id in surviving_before])

    treap = Treap(list(surviving_before))
    anchors = _Fenwick(m)
    for i, element_id in enumerate(surviving_before):
        if i in keep:
            anchors.add(target_pos[element_id], 1)

    kept_ids = _kept_ids(surviving_before, keep)
    movable = [element_id for element_id in surviving_after if element_id not in kept_ids]
    for element_id in movable:
        frm = treap.rank(element_id)
        treap.remove_at(frm)
        t = target_pos[element_id]
        below = anchors.prefix_sum(t)
        if below == 0:
            to = 0
        else:
            anchor_id = surviving_after[anchors.kth(below)]
            to = treap.rank(anchor_id) + 1
        treap.insert_at(to, element_id)
        anchors.add(t, 1)
        if to != frm:
            ops.append({
                "op": "move",
                "from": build_pointer(tokens + [str(frm)]),
                "path": build_pointer(tokens + [str(to)]),
            })
    assert treap.to_list() == surviving_after


def _kept_ids(surviving_before: List[str], keep: set) -> set:
    return {surviving_before[i] for i in keep}


def _lis_keep(seq: List[int]) -> set:
    """Indices of one longest strictly increasing subsequence of ``seq``."""
    tails: List[int] = []
    prev = [-1] * len(seq)
    for i, value in enumerate(seq):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if seq[tails[mid]] < value:
                lo = mid + 1
            else:
                hi = mid
        if lo:
            prev[i] = tails[lo - 1]
        if lo == len(tails):
            tails.append(i)
        else:
            tails[lo] = i
    keep = set()
    if tails:
        i = tails[-1]
        while i != -1:
            keep.add(i)
            i = prev[i]
    return keep


class _Fenwick:
    def __init__(self, n: int) -> None:
        self.n = n
        self.tree = [0] * (n + 1)

    def add(self, i: int, delta: int) -> None:
        i += 1
        while i <= self.n:
            self.tree[i] += delta
            i += i & -i

    def prefix_sum(self, i: int) -> int:
        """Sum of the first ``i`` slots (indices 0..i-1)."""
        total = 0
        while i > 0:
            total += self.tree[i]
            i -= i & -i
        return total

    def kth(self, k: int) -> int:
        """Index of the k-th set slot (1-indexed ``k``)."""
        pos = 0
        step = 1 << (self.n.bit_length())
        while step:
            nxt = pos + step
            if nxt <= self.n and self.tree[nxt] < k:
                k -= self.tree[nxt]
                pos = nxt
            step >>= 1
        return pos
