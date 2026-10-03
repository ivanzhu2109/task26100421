# ForgeKit schema diff

Python library that computes and replays RFC 6902 JSON Patches between two
immutable, already-parsed project-version documents.  No version storage,
no code generation.

## API

```python
from forgekit import diff, apply

patch = diff(before, after)     # RFC 6902 patch turning before into after
rollback = diff(after, before)  # swap arguments to get the rollback patch
result = apply(before, patch)   # replay; returns a new document
```

- `apply(before, diff(before, after))` is deep-equal to `after`.
- Neither function mutates its inputs; patch values do not alias the inputs.
- Output is deterministic: same inputs always produce the same patch, and
  identical documents produce an empty patch.
- Only the standard `add` / `remove` / `replace` / `move` ops are emitted,
  with RFC 6901 paths (`~` -> `~0`, `/` -> `~1`; empty and Unicode keys are
  supported).  `move` target indices follow RFC 6902: the source element is
  removed first, then inserted at `path`.

See `examples/usage.py` for a runnable demo.

## Diff semantics

- Objects and arrays at corresponding positions are compared recursively;
  `replace` is used only for leaf value changes or type changes.  `bool`
  and `int` are distinct types (`True` vs `1` is a `replace`).
- Array elements are matched by their string `id`, scoped to the containing
  array.  New ids produce exactly one element-level `add` (carrying the
  final content), departed ids exactly one `remove`.  Surviving ids are
  never deleted/recreated or wholesale replaced: their field changes are
  diffed recursively, and reordering uses `move` within the same array.
- The number of moves per array is minimal: `n - LIS`, where LIS is a
  longest subsequence of elements already in target-relative order.  Ties
  between optimal solutions are broken deterministically.

Op order inside an array diff: field edits of surviving elements (pathed by
before-index), removals (highest index first), moves (live indices against
the surviving-only sequence), insertions of new elements (ascending final
index).

## Complexity

For a single array of `n` elements, `diff` runs in **O(n log n)** time and
**O(n)** auxiliary space, including the cost of computing live move
indices:

- id matching, LIS (patience sorting) and a Fenwick tree over anchor
  positions are each O(n log n) or better;
- live `from`/`to` indices for every move are resolved against an implicit
  treap (O(log n) rank/remove/insert), not by splicing a Python list —
  so the index bookkeeping cannot degenerate to O(n^2);
- a fixed-seed RNG supplies treap priorities, keeping output deterministic.

Verified at n = 100,000 by `tests/test_perf.py` (fixed-seed full shuffle
and near-sorted reordering): measured growth is ~11-12x time and ~10.5x
peak memory for a 10x input increase, far below quadratic.  The scaling
requirement constrains `diff` only; `apply` uses plain list operations.

## Tests

```bash
python3 -m unittest discover -s tests
```

- `tests/test_exhaustive.py` — every permutation of <= 7 elements: replay
  correctness and provably minimal move counts, including the
  first-to-last single-move case.
- `tests/test_nested.py` — nested arrays reordering while elements are
  added/removed/edited, special key names, ids reused across arrays,
  bool-to-int changes, stepwise forward and rollback replay, plus
  handwritten patches pinning down move index semantics.
- `tests/test_roundtrip.py` — determinism, immutability, aliasing, type
  strictness, escaping.
- `tests/test_perf.py` — 100k-element scaling and peak-memory checks.
