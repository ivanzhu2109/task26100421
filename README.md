# ForgeKit Schema Diff

A small Python library for showing changes between immutable project
versions as [RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)
patches, with rollback support.  Callers pass two already-parsed, valid
JSON documents; the library does not store versions or generate code.

## API

```python
from forgekit import diff, apply

patch = diff(before, after)     # RFC 6902 ops turning before into after
rollback = diff(after, before)  # swap arguments to roll back
result = apply(document, patch) # replay a patch, returns a new document
```

Guarantees:

- `apply(before, diff(before, after))` is deep-equal to `after`.
- Neither `diff` nor `apply` mutates its inputs.
- Identical inputs produce identical patches; equal documents produce an
  empty patch.
- Only the standard `add` / `remove` / `replace` / `move` ops are emitted,
  with RFC 6901 paths (`~` → `~0`, `/` → `~1`).

## Diff semantics

- **Objects** are compared recursively: new keys → `add`, vanished keys →
  `remove`, changed leaves or changed value types → `replace`.  Booleans
  and integers are distinct types (`true` → `1` is a `replace`).
- **Arrays** contain objects with string `id`s; identity is the `id`
  within that array only.  New ids produce exactly one element-level
  `add` (carrying the final content), vanished ids exactly one
  element-level `remove`.  Surviving ids are never deleted/recreated or
  wholesale replaced: their fields are diffed recursively, and
  reordering is expressed with `move` ops inside the same array.
- **Moves are minimal**: for each array the number of `move` ops equals
  `survivors − LIS`, where LIS is a longest subsequence of surviving ids
  already in relative order.  This is provably the minimum; ties are
  broken deterministically.  A `move`'s destination index is interpreted
  against the array after the source element is removed (RFC 6902).

## Complexity

For a single array of `n` elements that is purely reordered, `diff`
runs in **O(n log n)** time and **O(n)** auxiliary space, and handles
`n = 100,000`:

- id matching and survivor extraction: hash maps, O(n);
- minimal-move selection: patience-sorting LIS, O(n log n);
- live `from`/`to` index computation: an implicit treap simulates the
  survivor sequence, giving O(log n) per `remove_at`/`insert_at`/
  `index_of` instead of O(n) list splicing — so the index bookkeeping is
  included in the O(n log n) bound, not just the identity matching.

`apply` replays ops on Python lists (O(n) per array splice); the 100k
scaling requirement constrains `diff` only.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

- `tests/test_exhaustive.py` — every permutation of ≤ 7 elements:
  replay correctness plus exact minimal move counts (oracle: independent
  O(n²) LIS DP), including the head-to-tail single-move case.
- `tests/test_diff_apply.py` — nested arrays reordering while elements
  are added/removed/edited, special key names (`""`, `/`, `~`, unicode),
  id reuse across arrays, bool→int replaces, forward + rollback
  step-by-step replay, and hand-written patches pinning down same-array
  move index semantics.
- `tests/test_perf.py` — fixed-seed full shuffle and nearly-ordered
  reorder at 10k and 100k elements, comparing wall time and peak memory
  to expose quadratic behaviour.

## Example

```bash
python3 examples/usage.py
```
