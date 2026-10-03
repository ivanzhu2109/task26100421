"""Schema diff: compute an RFC 6902 patch between two JSON documents.

Array elements are objects carrying a string ``id``; identity is tracked by
``id`` within each array.  Surviving ids are never removed/recreated or
wholesale replaced: their fields are diffed recursively and reordering is
expressed with a minimal number of in-array ``move`` operations
(``len(survivors) - len(LIS)`` moves, computed with an implicit treap so a
pure reorder of n elements costs O(n log n) time and O(n) space).
"""

import copy
from typing import Any, Dict, List

from ._lis import lis_membership
from ._treap import ImplicitTreap


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _diff_value(before: Any, after: Any, path: str, ops: List[Dict[str, Any]]) -> None:
    if type(before) is not type(after):
        # Leaf change or value-type change (bool and int are distinct types).
        ops.append({"op": "replace", "path": path, "value": copy.deepcopy(after)})
        return
    if isinstance(before, dict):
        _diff_object(before, after, path, ops)
    elif isinstance(before, list):
        _diff_array(before, after, path, ops)
    elif before != after:
        ops.append({"op": "replace", "path": path, "value": copy.deepcopy(after)})


def _diff_object(before: dict, after: dict, path: str, ops: List[Dict[str, Any]]) -> None:
    for key, old_value in before.items():
        child_path = path + "/" + _escape(key)
        if key not in after:
            ops.append({"op": "remove", "path": child_path})
        else:
            _diff_value(old_value, after[key], child_path, ops)
    for key, new_value in after.items():
        if key not in before:
            ops.append({"op": "add", "path": path + "/" + _escape(key),
                        "value": copy.deepcopy(new_value)})


def _diff_array(before: list, after: list, path: str, ops: List[Dict[str, Any]]) -> None:
    before_ids = [element["id"] for element in before]
    after_ids = [element["id"] for element in after]
    after_pos = {element_id: index for index, element_id in enumerate(after_ids)}
    before_pos = {element_id: index for index, element_id in enumerate(before_ids)}

    # 1. Field-level edits of surviving ids, addressed by before-indices.
    for index, element in enumerate(before):
        target = after_pos.get(element["id"])
        if target is not None:
            _diff_object(element, after[target], f"{path}/{index}", ops)

    # 2. Remove vanished ids, highest before-index first so earlier
    #    indices stay valid.
    for index in range(len(before) - 1, -1, -1):
        if before_ids[index] not in after_pos:
            ops.append({"op": "remove", "path": f"{path}/{index}"})

    # 3. Reorder survivors with a minimal number of moves: everything
    #    outside one LIS (in before-rank order) moves exactly once.
    survivors_before = [eid for eid in before_ids if eid in after_pos]
    survivors_after = [eid for eid in after_ids if eid in before_pos]
    before_rank = {eid: rank for rank, eid in enumerate(survivors_before)}
    sequence = [before_rank[eid] for eid in survivors_after]
    in_lis = lis_membership(sequence)
    treap = ImplicitTreap(survivors_before)
    for target_index, element_id in enumerate(survivors_after):
        if in_lis[target_index]:
            continue
        from_index = treap.index_of(element_id)
        treap.remove_at(from_index)
        if target_index == 0:
            to_index = 0
        else:
            to_index = treap.index_of(survivors_after[target_index - 1]) + 1
        treap.insert_at(to_index, element_id)
        ops.append({"op": "move", "from": f"{path}/{from_index}",
                    "path": f"{path}/{to_index}"})

    # 4. Add new ids at their final after-indices (ascending, so each
    #    insertion lands exactly at its final position).
    for index, element in enumerate(after):
        if element["id"] not in before_pos:
            ops.append({"op": "add", "path": f"{path}/{index}",
                        "value": copy.deepcopy(element)})


def diff(before: Any, after: Any) -> List[Dict[str, Any]]:
    """Return an RFC 6902 patch transforming ``before`` into ``after``.

    Uses only add/remove/replace/move with RFC 6901 paths.  Neither input
    is modified; identical inputs always yield the identical patch, and
    equal documents yield an empty patch.
    """
    ops: List[Dict[str, Any]] = []
    _diff_value(before, after, "", ops)
    return ops
