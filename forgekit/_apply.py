"""RFC 6902 patch replay (add / remove / replace / move)."""

import copy
from typing import Any, List, Mapping, Sequence

from typing import Dict  # noqa: F401  (re-exported for type users)


class PatchError(ValueError):
    """Raised when a patch operation cannot be applied."""


def _parse_pointer(path: Any) -> List[str]:
    if not isinstance(path, str):
        raise PatchError(f"patch path must be a string, got {type(path).__name__}")
    if path == "":
        return []
    if not path.startswith("/"):
        raise PatchError(f"invalid JSON pointer: {path!r}")
    return [token.replace("~1", "/").replace("~0", "~") for token in path.split("/")[1:]]


def _array_index(token: str, length: int, allow_end: bool, allow_dash: bool) -> int:
    if token == "-":
        if allow_dash:
            return length
        raise PatchError("'-' is only valid for add")
    if not token.isdigit():
        raise PatchError(f"invalid array index: {token!r}")
    index = int(token)
    upper = length if allow_end else length - 1
    if index > upper:
        raise PatchError(f"array index {index} out of range (length {length})")
    return index


def _child(container: Any, token: str) -> Any:
    if isinstance(container, list):
        index = _array_index(token, len(container), allow_end=False, allow_dash=False)
        return container[index]
    if isinstance(container, dict):
        if token not in container:
            raise PatchError(f"object key not found: {token!r}")
        return container[token]
    raise PatchError(f"cannot descend into {type(container).__name__}")


def _remove(container: Any, token: str) -> Any:
    if isinstance(container, list):
        index = _array_index(token, len(container), allow_end=False, allow_dash=False)
        return container.pop(index)
    if isinstance(container, dict):
        if token not in container:
            raise PatchError(f"object key not found: {token!r}")
        return container.pop(token)
    raise PatchError(f"cannot remove from {type(container).__name__}")


def _add(container: Any, token: str, value: Any) -> None:
    if isinstance(container, list):
        index = _array_index(token, len(container), allow_end=True, allow_dash=True)
        container.insert(index, value)
        return
    if isinstance(container, dict):
        container[token] = value
        return
    raise PatchError(f"cannot add to {type(container).__name__}")


def _replace(container: Any, token: str, value: Any) -> None:
    if isinstance(container, list):
        index = _array_index(token, len(container), allow_end=False, allow_dash=False)
        container[index] = value
        return
    if isinstance(container, dict):
        if token not in container:
            raise PatchError(f"object key not found: {token!r}")
        container[token] = value
        return
    raise PatchError(f"cannot replace in {type(container).__name__}")


def _resolve_parent(root: Any, tokens: List[str]) -> Any:
    node = root
    for token in tokens[:-1]:
        node = _child(node, token)
    return node


def _apply_op(root: Any, op: Mapping[str, Any]) -> Any:
    kind = op.get("op")
    if kind == "move":
        if "from" not in op:
            raise PatchError("move requires 'from'")
        from_tokens = _parse_pointer(op["from"])
        path_tokens = _parse_pointer(op.get("path"))
        if not from_tokens:
            raise PatchError("cannot move the document root")
        if from_tokens == path_tokens:
            return root
        if path_tokens[: len(from_tokens)] == from_tokens:
            raise PatchError("cannot move a value into its own descendant")
        value = _remove(_resolve_parent(root, from_tokens), from_tokens[-1])
        if not path_tokens:
            return value
        _add(_resolve_parent(root, path_tokens), path_tokens[-1], value)
        return root
    if kind == "remove":
        tokens = _parse_pointer(op.get("path"))
        if not tokens:
            raise PatchError("cannot remove the document root")
        _remove(_resolve_parent(root, tokens), tokens[-1])
        return root
    if kind == "add":
        tokens = _parse_pointer(op.get("path"))
        value = copy.deepcopy(op.get("value"))
        if not tokens:
            return value
        _add(_resolve_parent(root, tokens), tokens[-1], value)
        return root
    if kind == "replace":
        tokens = _parse_pointer(op.get("path"))
        value = copy.deepcopy(op.get("value"))
        if not tokens:
            return value
        _replace(_resolve_parent(root, tokens), tokens[-1], value)
        return root
    raise PatchError(f"unsupported operation: {kind!r}")


def apply(document: Any, patch: Sequence[Mapping[str, Any]]) -> Any:
    """Apply an RFC 6902 patch and return a new document.

    Operations are replayed in order with RFC 6902 semantics; a ``move``
    removes the source first and inserts at the destination index of the
    resulting document.  Neither ``document`` nor ``patch`` is modified.
    """
    root = copy.deepcopy(document)
    for op in patch:
        root = _apply_op(root, op)
    return root
