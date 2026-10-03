"""Nested diffs, special key names, id reuse across arrays, rollback,
and handwritten-patch move semantics."""

import copy
import unittest

from forgekit import PatchError, apply, diff


def replay_stepwise(document, patch):
    """Apply ops one at a time, returning all intermediate documents."""
    states = [document]
    for op in patch:
        states.append(apply(states[-1], [op]))
    return states


class TestNestedDiff(unittest.TestCase):
    def setUp(self):
        # Special key names: empty string, slash, tilde, unicode.
        # The id "shared" is reused across two different arrays.
        self.before = {
            "": {"~/键": "leaf"},
            "a/b": [
                {"id": "shared", "flag": True, "val": 1},
                {"id": "gone", "val": 2},
                {"id": "尾", "val": 3},
            ],
            "tilde~key": [
                {"id": "shared", "nested": [{"id": "n1", "x": 1}, {"id": "n2", "x": 2}]},
                {"id": "other", "nested": []},
            ],
        }
        self.after = {
            "": {"~/键": "changed"},
            "a/b": [
                {"id": "尾", "val": 3},
                {"id": "shared", "flag": 1, "val": 1},   # bool -> int
                {"id": "new/元素", "val": 4},             # added element
            ],
            "tilde~key": [
                {"id": "other", "nested": [{"id": "n9", "x": 9}]},
                {"id": "shared", "nested": [{"id": "n2", "x": 2}, {"id": "n1", "x": 1}]},
            ],
            "brand new": None,
        }

    def test_forward_and_rollback(self):
        before, after = self.before, self.after
        before_snapshot = copy.deepcopy(before)
        after_snapshot = copy.deepcopy(after)

        forward = diff(before, after)
        rollback = diff(after, before)

        # Step-by-step replay in both directions must succeed and land
        # exactly on the target document.
        for state in replay_stepwise(before, forward)[1:]:
            self.assertIsNot(state, before)
        self.assertEqual(replay_stepwise(before, forward)[-1], after)
        self.assertEqual(replay_stepwise(after, rollback)[-1], before)

        # diff/apply must not mutate their inputs.
        self.assertEqual(before, before_snapshot)
        self.assertEqual(after, after_snapshot)

        # Determinism.
        self.assertEqual(forward, diff(before, after))
        self.assertEqual(rollback, diff(after, before))

    def test_patch_shape(self):
        forward = diff(self.before, self.after)

        # bool -> int is a replace of the leaf, not an element rebuild.
        self.assertIn({"op": "replace", "path": "/a~1b/0/flag", "value": 1}, forward)
        # Vanished id produces exactly one element-level remove.
        removes = [op for op in forward if op["op"] == "remove" and op["path"].count("/") == 2]
        self.assertEqual(removes, [{"op": "remove", "path": "/a~1b/1"}])
        # New id produces exactly one element-level add carrying final content.
        adds = [op for op in forward if op["op"] == "add" and op["path"].startswith("/a~1b/")]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0]["value"], {"id": "new/元素", "val": 4})
        # Surviving ids are never removed/recreated or wholesale replaced:
        # no op targets an array element as a whole except the single
        # element-level remove/add of the genuinely vanished/new ids.
        import re
        element_path = re.compile(r"^/(a~1b|tilde~0key)/\d+$")
        element_ops = [op for op in forward if element_path.match(op["path"])]
        for op in element_ops:
            self.assertNotEqual(op["op"], "replace")
        self.assertEqual(
            sorted((op["op"], op["path"]) for op in element_ops if op["op"] != "move"),
            [("add", "/a~1b/2"), ("remove", "/a~1b/1")])
        # Nested array reordered with a single move (n1/n2 swap of 2 elements).
        nested_moves = [op for op in forward
                        if op["op"] == "move" and op["path"].startswith("/tilde~0key/")]
        self.assertEqual(len(nested_moves), 2)  # one per reordered array level
        # Special keys are RFC 6901 escaped in paths.
        paths = [op.get("path", "") for op in forward] + [op.get("from", "") for op in forward]
        self.assertTrue(any(p.startswith("/a~1b/") for p in paths))
        self.assertTrue(any(p.startswith("/tilde~0key/") for p in paths))
        self.assertTrue(any(p.startswith("//~0~1键") for p in paths))

    def test_id_reuse_across_arrays(self):
        # "shared" lives in both arrays; each array tracks its own ids.
        forward = diff(self.before, self.after)
        # a/b: "shared" survives (field edit only), tilde~key: "shared" survives.
        for op in forward:
            if op["op"] in ("add", "remove") and op["path"].count("/") == 2:
                self.assertNotIn("shared", str(op.get("value", "")))


class TestHandwrittenMoveSemantics(unittest.TestCase):
    """Move index semantics verified with hand-written patches, not just
    diff/apply round-trips."""

    def test_same_array_move_forward(self):
        doc = {"arr": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]}
        # Remove index 0 -> [b, c, d]; insert at 2 -> [b, c, a, d].
        out = apply(doc, [{"op": "move", "from": "/arr/0", "path": "/arr/2"}])
        self.assertEqual([e["id"] for e in out["arr"]], ["b", "c", "a", "d"])

    def test_same_array_move_backward(self):
        doc = {"arr": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]}
        # Remove index 3 -> [a, b, c]; insert at 1 -> [a, d, b, c].
        out = apply(doc, [{"op": "move", "from": "/arr/3", "path": "/arr/1"}])
        self.assertEqual([e["id"] for e in out["arr"]], ["a", "d", "b", "c"])

    def test_move_to_end_uses_post_removal_length(self):
        doc = {"arr": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
        # After removing index 0 the array has length 2; index 2 is the end.
        out = apply(doc, [{"op": "move", "from": "/arr/0", "path": "/arr/2"}])
        self.assertEqual([e["id"] for e in out["arr"]], ["b", "c", "a"])

    def test_move_across_arrays(self):
        doc = {"x": [{"id": "a"}], "y": [{"id": "b"}]}
        out = apply(doc, [{"op": "move", "from": "/x/0", "path": "/y/1"}])
        self.assertEqual(out, {"x": [], "y": [{"id": "b"}, {"id": "a"}]})

    def test_move_into_own_descendant_rejected(self):
        doc = {"a": {"b": 1}}
        with self.assertRaises(PatchError):
            apply(doc, [{"op": "move", "from": "/a", "path": "/a/c"}])

    def test_escaped_move_paths(self):
        doc = {"a/b": [{"id": "~x"}, {"id": "y/"}]}
        out = apply(doc, [{"op": "move", "from": "/a~1b/1", "path": "/a~1b/0"}])
        self.assertEqual([e["id"] for e in out["a/b"]], ["y/", "~x"])


class TestLeafAndTypeChanges(unittest.TestCase):
    def test_bool_int_distinct(self):
        self.assertEqual(diff({"f": True}, {"f": 1}),
                         [{"op": "replace", "path": "/f", "value": 1}])
        self.assertEqual(diff({"f": 0}, {"f": False}),
                         [{"op": "replace", "path": "/f", "value": False}])
        self.assertEqual(diff({"f": True}, {"f": True}), [])
        self.assertEqual(diff({"f": 1}, {"f": 1}), [])

    def test_null_and_string(self):
        self.assertEqual(diff({"f": None}, {"f": "null"}),
                         [{"op": "replace", "path": "/f", "value": "null"}])
        self.assertEqual(diff({"f": "a"}, {"f": "a"}), [])

    def test_type_change_container(self):
        patch = diff({"f": {"a": 1}}, {"f": [{"id": "x"}]})
        self.assertEqual(patch, [{"op": "replace", "path": "/f",
                                  "value": [{"id": "x"}]}])
        self.assertEqual(apply({"f": {"a": 1}}, patch), {"f": [{"id": "x"}]})

    def test_object_key_add_remove(self):
        patch = diff({"a": 1, "b": 2}, {"b": 2, "c": 3})
        self.assertEqual(patch, [
            {"op": "remove", "path": "/a"},
            {"op": "add", "path": "/c", "value": 3},
        ])

    def test_empty_arrays_and_objects(self):
        self.assertEqual(diff({"a": []}, {"a": []}), [])
        self.assertEqual(diff({}, {}), [])
        patch = diff({"a": []}, {"a": [{"id": "x", "v": 1}]})
        self.assertEqual(patch, [{"op": "add", "path": "/a/0",
                                  "value": {"id": "x", "v": 1}}])
        self.assertEqual(apply({"a": []}, patch), {"a": [{"id": "x", "v": 1}]})

    def test_deep_equality_not_identity(self):
        before = {"items": [{"id": "a", "tags": {"x": [{"id": "t1"}, {"id": "t2"}]}}]}
        after = copy.deepcopy(before)
        self.assertEqual(diff(before, after), [])


if __name__ == "__main__":
    unittest.main()
