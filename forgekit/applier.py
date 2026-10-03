"""Replay an RFC 6902 patch, returning a new document."""

from copy import deepcopy
from typing import Any, Dict, List

from forgekit.pointer import parse_pointer

Json = Any
Op = Dict[str, Any]


def apply(document: Json, patch: List[Op]) -> Json:
    """Apply ``patch`` to ``document`` per RFC 6902 and return the result.

    Neither ``document`` nor ``patch`` is mutated.
    """
    result = deepcopy(document)
    for op in patch:
        result = _apply_op(result, op)
    return result


def _apply_op(document: Json, op: Op) -> Json:
    kind = op.get("op")
    if kind == "add":
        return _add(document, parse_pointer(op["path"]), deepcopy(op["value"]))
    if kind == "remove":
        return _remove(document, parse_pointer(op["path"]))
    if kind == "replace":
        return _replace(document, parse_pointer(op["path"]), deepcopy(op["value"]))
    if kind == "move":
        # ``from`` is removed first, so ``path`` is interpreted against the
        # document *after* removal of the source element (RFC 6902 §4.4).
        source = parse_pointer(op["from"])
        value = _resolve(document, source)
        document = _remove(document, source)
        return _add(document, parse_pointer(op["path"]), value)
    raise ValueError(f"unsupported op: {kind!r}")


def _resolve(document: Json, tokens: List[str]) -> Json:
    node = document
    for token in tokens:
        node = _child(node, token)
    return node


def _child(node: Json, token: str) -> Json:
    if isinstance(node, dict):
        if token not in node:
            raise KeyError(f"no such object key: {token!r}")
        return node[token]
    if isinstance(node, list):
        return node[_index(token, len(node))]
    raise TypeError(f"cannot descend into {type(node).__name__}")


def _index(token: str, length: int, allow_end: bool = False) -> int:
    if not token.isdigit():
        raise ValueError(f"invalid array index: {token!r}")
    index = int(token)
    upper = length if allow_end else length - 1
    if index > upper:
        raise IndexError(f"array index {index} out of range (length {length})")
    return index


def _add(document: Json, tokens: List[str], value: Json) -> Json:
    if not tokens:
        return value
    parent = _resolve(document, tokens[:-1])
    token = tokens[-1]
    if isinstance(parent, dict):
        parent[token] = value
    elif isinstance(parent, list):
        if token == "-":
            parent.append(value)
        else:
            parent.insert(_index(token, len(parent), allow_end=True), value)
    else:
        raise TypeError(f"cannot add into {type(parent).__name__}")
    return document


def _remove(document: Json, tokens: List[str]) -> Json:
    if not tokens:
        raise ValueError("cannot remove the document root")
    parent = _resolve(document, tokens[:-1])
    token = tokens[-1]
    if isinstance(parent, dict):
        if token not in parent:
            raise KeyError(f"no such object key: {token!r}")
        del parent[token]
    elif isinstance(parent, list):
        parent.pop(_index(token, len(parent)))
    else:
        raise TypeError(f"cannot remove from {type(parent).__name__}")
    return document


def _replace(document: Json, tokens: List[str], value: Json) -> Json:
    if not tokens:
        return value
    parent = _resolve(document, tokens[:-1])
    token = tokens[-1]
    if isinstance(parent, dict):
        if token not in parent:
            raise KeyError(f"no such object key: {token!r}")
        parent[token] = value
    elif isinstance(parent, list):
        parent[_index(token, len(parent))] = value
    else:
        raise TypeError(f"cannot replace inside {type(parent).__name__}")
    return document
