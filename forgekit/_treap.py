"""Implicit treap: a sequence supporting O(log n) expected index operations.

The array differ uses this to compute live ``from``/``to`` indices for
``move`` operations, avoiding O(n) list splicing per move.  Priorities come
from a fixed-seed PRNG so results are deterministic across runs.
"""

import random
from typing import Any, Dict, List, Optional


class _Node:
    __slots__ = ("value", "priority", "size", "left", "right", "parent")

    def __init__(self, value: Any, priority: int) -> None:
        self.value = value
        self.priority = priority
        self.size = 1
        self.left: Optional["_Node"] = None
        self.right: Optional["_Node"] = None
        self.parent: Optional["_Node"] = None


def _size(node: Optional[_Node]) -> int:
    return node.size if node is not None else 0


def _update(node: _Node) -> None:
    node.size = 1 + _size(node.left) + _size(node.right)


def _split(root: Optional[_Node], k: int):
    """Split into (first k nodes, rest)."""
    if root is None:
        return (None, None)
    left_size = _size(root.left)
    if left_size >= k:
        left, right = _split(root.left, k)
        root.left = right
        if right is not None:
            right.parent = root
        _update(root)
        root.parent = None
        return (left, root)
    left, right = _split(root.right, k - left_size - 1)
    root.right = left
    if left is not None:
        left.parent = root
    _update(root)
    root.parent = None
    return (root, right)


def _merge(a: Optional[_Node], b: Optional[_Node]) -> Optional[_Node]:
    if a is None:
        if b is not None:
            b.parent = None
        return b
    if b is None:
        a.parent = None
        return a
    if a.priority > b.priority:
        child = _merge(a.right, b)
        a.right = child
        if child is not None:
            child.parent = a
        _update(a)
        a.parent = None
        return a
    child = _merge(a, b.left)
    b.left = child
    if child is not None:
        child.parent = b
    _update(b)
    b.parent = None
    return b


class ImplicitTreap:
    """A mutable sequence with O(log n) expected index_of/remove/insert."""

    def __init__(self, values: List[Any]) -> None:
        self._rng = random.Random(0xF06E)
        self._nodes: Dict[Any, _Node] = {}
        self._root: Optional[_Node] = None
        for value in values:
            node = self._make_node(value)
            self._root = _merge(self._root, node)

    def _make_node(self, value: Any) -> _Node:
        node = _Node(value, self._rng.getrandbits(64))
        self._nodes[value] = node
        return node

    def __len__(self) -> int:
        return _size(self._root)

    def index_of(self, value: Any) -> int:
        node = self._nodes[value]
        index = _size(node.left)
        parent = node.parent
        while parent is not None:
            if parent.right is node:
                index += _size(parent.left) + 1
            node = parent
            parent = node.parent
        return index

    def remove_at(self, index: int) -> Any:
        left, rest = _split(self._root, index)
        node, right = _split(rest, 1)
        self._root = _merge(left, right)
        value = node.value
        del self._nodes[value]
        node.left = node.right = node.parent = None
        return value

    def insert_at(self, index: int, value: Any) -> None:
        node = self._make_node(value)
        left, right = _split(self._root, index)
        self._root = _merge(_merge(left, node), right)
