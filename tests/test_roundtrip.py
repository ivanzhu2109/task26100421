"""Basic diff/apply semantics: roundtrip, determinism, immutability, typing."""

import copy
import unittest

from forgekit import apply, diff


def doc_with_array(ids):
    return {"items": [{"id": i} for i in ids]}


class RoundtripTest(unittest.TestCase):
    def test_empty_patch_for_identical_documents(self):
        doc = {"a": [{"id": "x", "b": None}], "c": {"d": True}}
        self.assertEqual(diff(doc, copy.deepcopy(doc)), [])

    def test_diff_is_deterministic(self):
        before = {"arr": [{"id": c, "n": i} for i, c in enumerate("abcdef")], "k": 1}
        after = {"arr": [{"id": c, "n": i + 1} for i, c in enumerate("facbd")], "k": 2, "x": []}
        self.assertEqual(diff(before, after), diff(before, after))

    def test_roundtrip_and_rollback(self):
        before = {"arr": [{"id": c, "n": 0} for c in "abcde"], "meta": {"v": 1}}
        after = {"arr": [{"id": c, "n": 1} for c in "caebd"], "meta": {"v": 2}, "new": []}
        forward = diff(before, after)
        backward = diff(after, before)
        self.assertEqual(apply(before, forward), after)
        self.assertEqual(apply(after, backward), before)

    def test_inputs_are_not_mutated(self):
        before = {"arr": [{"id": "a", "v": 1}], "x": 1}
        after = {"arr": [{"id": "a", "v": 2}, {"id": "b"}], "x": 2}
        before_snapshot = copy.deepcopy(before)
        after_snapshot = copy.deepcopy(after)
        patch = diff(before, after)
        patch_snapshot = copy.deepcopy(patch)
        apply(before, patch)
        self.assertEqual(before, before_snapshot)
        self.assertEqual(after, after_snapshot)
        self.assertEqual(patch, patch_snapshot)

    def test_patch_values_do_not_alias_inputs(self):
        after = {"obj": {"nested": {"y": [1]}}, "arr": [{"id": "n", "payload": {"x": 1}}]}
        patch = diff({}, after)
        result = apply({}, patch)
        result["obj"]["nested"]["y"].append(2)
        result["arr"][0]["payload"]["x"] = 9
        self.assertEqual(after, {"obj": {"nested": {"y": [1]}}, "arr": [{"id": "n", "payload": {"x": 1}}]})

    def test_bool_is_not_int(self):
        self.assertEqual(diff({"v": True}, {"v": 1}),
                         [{"op": "replace", "path": "/v", "value": 1}])
        self.assertEqual(diff({"v": 0}, {"v": False}),
                         [{"op": "replace", "path": "/v", "value": False}])
        self.assertEqual(diff({"v": True}, {"v": True}), [])

    def test_type_change_uses_replace(self):
        self.assertEqual(diff({"v": [{"id": "i"}]}, {"v": {"a": 1}}),
                         [{"op": "replace", "path": "/v", "value": {"a": 1}}])
        self.assertEqual(diff({"v": {"a": 1}}, {"v": "text"}),
                         [{"op": "replace", "path": "/v", "value": "text"}])
        self.assertEqual(diff({"v": None}, {"v": 0}),
                         [{"op": "replace", "path": "/v", "value": 0}])

    def test_objects_recurse_instead_of_replace(self):
        before = {"o": {"keep": 1, "drop": 2, "chg": 3}}
        after = {"o": {"keep": 1, "chg": 4, "add": 5}}
        patch = diff(before, after)
        self.assertEqual(
            patch,
            [
                {"op": "remove", "path": "/o/drop"},
                {"op": "replace", "path": "/o/chg", "value": 4},
                {"op": "add", "path": "/o/add", "value": 5},
            ],
        )

    def test_arrays_recurse_instead_of_replace(self):
        before = {"a": [{"id": "x", "v": 1}, {"id": "y", "v": 2}]}
        after = {"a": [{"id": "y", "v": 2}, {"id": "x", "v": 3}]}
        patch = diff(before, after)
        self.assertNotIn("replace", {op["op"] for op in patch if op["path"] == "/a"})
        self.assertEqual(apply(before, patch), after)

    def test_special_key_names(self):
        before = {"": 1, "a/b": 2, "~tilde": 3, "雪": 4, "~0/~1": 5}
        after = {"": 0, "a/b": 2, "~tilde": 4, "雪": 4, "~0/~1": 5, "新/键~": None}
        patch = diff(before, after)
        self.assertEqual(apply(before, patch), after)
        paths = {op["path"] for op in patch}
        self.assertIn("/", paths)            # empty key
        self.assertIn("/~0tilde", paths)     # tilde escaped
        self.assertIn("/新~1键~0", paths)    # slash and tilde escaped

    def test_special_id_values(self):
        before = doc_with_array(["", "a/b", "~", "雪"])
        after = doc_with_array(["雪", "~", "", "a/b"])
        patch = diff(before, after)
        self.assertEqual(apply(before, patch), after)
        moves = [op for op in patch if op["op"] == "move"]
        self.assertEqual(len(moves), 2)  # n - LIS = 4 - 2

    def test_empty_arrays(self):
        self.assertEqual(diff({"a": []}, {"a": []}), [])
        before = {"a": [], "b": [{"id": "x"}]}
        after = {"a": [{"id": "y", "v": 1}], "b": []}
        patch = diff(before, after)
        self.assertEqual(apply(before, patch), after)

    def test_surviving_ids_are_not_rebuilt(self):
        before = doc_with_array(["a", "b", "c"])
        after = doc_with_array(["c", "b", "a"])
        patch = diff(before, after)
        kinds = {(op["op"], op.get("path", "").rsplit("/", 1)[0]) for op in patch}
        # no element-level add/remove for surviving ids, only moves
        self.assertEqual([op for op in patch if op["op"] in ("add", "remove")], [])
        self.assertTrue(all(op["op"] == "move" for op in patch))
        self.assertEqual(len(patch), 2)  # n - LIS = 3 - 1
        self.assertEqual(apply(before, patch), after)


if __name__ == "__main__":
    unittest.main()
