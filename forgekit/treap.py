"""Randomized implicit-key treap with O(log n) rank / remove-at / insert-at.

Used by the array differ to compute live ``move`` indices in O(n log n)
overall.  Priorities come from a fixed-seed RNG so output is deterministic.
"""

import random
from typing import Any, Dict, List, Optional

_RNG_SEED = 0xF086E17


class _Node:
    __slots__ = ("key", "prio", "left", "right", "parent", "size")

    def __init__(self, key: Any, prio: float) -> None:
        self.key = key
        self.prio = prio
        self.left: Optional["_Node"] = None
        self.right: Optional["_Node"] = None
        self.parent: Optional["_Node"] = None
        self.size = 1


class Treap:
    """Implicit treap over a sequence of hashable keys."""

    def __init__(self, keys: List[Any]) -> None:
        rng = random.Random(_RNG_SEED)
        self._nodes: Dict[Any, _Node] = {}
        self._root: Optional[_Node] = None
        if not keys:
            return
        stack: List[_Node] = []
        for key in keys:
            node = _Node(key, rng.random())
            self._nodes[key] = node
            last: Optional[_Node] = None
            while stack and stack[-1].prio < node.prio:
                last = stack.pop()
            node.left = last
            if last is not None:
                last.parent = node
            if stack:
                stack[-1].right = node
                node.parent = stack[-1]
            stack.append(node)
        self._root = stack[0]
        self._root.parent = None
        self._recompute_sizes()

    def _recompute_sizes(self) -> None:
        root = self._root
        if root is None:
            return
        order: List[_Node] = []
        stack = [root]
        while stack:
            node = stack.pop()
            order.append(node)
            if node.left is not None:
                stack.append(node.left)
            if node.right is not None:
                stack.append(node.right)
        for node in reversed(order):
            _update(node)

    def __len__(self) -> int:
        return _size(self._root)

    def rank(self, key: Any) -> int:
        """Current 0-based position of ``key``."""
        node = self._nodes[key]
        result = _size(node.left)
        while node.parent is not None:
            parent = node.parent
            if node is parent.right:
                result += _size(parent.left) + 1
            node = parent
        return result

    def remove_at(self, index: int) -> Any:
        """Remove the element at ``index`` and return its key."""
        left, rest = _split(self._root, index)
        target, right = _split(rest, 1)
        assert target is not None
        self._root = _merge(left, right)
        if self._root is not None:
            self._root.parent = None
        return target.key

    def insert_at(self, index: int, key: Any) -> None:
        """Insert ``key`` so that it ends up at position ``index``."""
        node = self._nodes.get(key)
        if node is None:
            raise KeyError(f"cannot insert unknown key: {key!r}")
        node.left = node.right = node.parent = None
        node.size = 1
        left, right = _split(self._root, index)
        self._root = _merge(_merge(left, node), right)
        if self._root is not None:
            self._root.parent = None

    def to_list(self) -> List[Any]:
        """In-order traversal of the current sequence."""
        result: List[Any] = []
        stack: List[_Node] = []
        node = self._root
        while stack or node is not None:
            while node is not None:
                stack.append(node)
                node = node.left
            node = stack.pop()
            result.append(node.key)
            node = node.right
        return result


def _size(node: Optional[_Node]) -> int:
    return node.size if node is not None else 0


def _update(node: _Node) -> None:
    node.size = _size(node.left) + _size(node.right) + 1


def _split(node: Optional[_Node], k: int) -> "tuple[Optional[_Node], Optional[_Node]]":
    """Split into (first k nodes, rest)."""
    if node is None:
        return (None, None)
    if k <= _size(node.left):
        left, right = _split(node.left, k)
        node.left = right
        if right is not None:
            right.parent = node
        _update(node)
        node.parent = None
        if left is not None:
            left.parent = None
        return (left, node)
    left, right = _split(node.right, k - _size(node.left) - 1)
    node.right = left
    if left is not None:
        left.parent = node
    _update(node)
    node.parent = None
    if right is not None:
        right.parent = None
    return (node, right)


def _merge(a: Optional[_Node], b: Optional[_Node]) -> Optional[_Node]:
    if a is None:
        return b
    if b is None:
        return a
    if a.prio > b.prio:
        a.right = _merge(a.right, b)
        if a.right is not None:
            a.right.parent = a
        _update(a)
        return a
    b.left = _merge(a, b.left)
    if b.left is not None:
        b.left.parent = b
    _update(b)
    return b
