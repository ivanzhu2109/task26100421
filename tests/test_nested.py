"""Nested structures: simultaneous reorder/add/remove/field edits, special
keys, id reuse across arrays, bool->int, forward & rollback step replay,
and handwritten patches pinning down RFC 6902 move index semantics.
"""

import unittest

from forgekit import apply, diff

BEFORE = {
    "": {"~key/雪": "v"},
    "modules": [
        {"id": "core", "version": 1, "enabled": True,
         "deps": [{"id": "a"}, {"id": "b"}, {"id": "c"}]},
        {"id": "ui/主界面", "version": 3, "flag": False,
         "deps": [{"id": "a"}, {"id": "x"}]},
        {"id": "old", "version": 9, "deps": []},
    ],
    "plugins~1": [
        {"id": "core", "note": "id shared with /modules, scoped per array"},
        {"id": "p/2", "tags": [{"id": "t1"}, {"id": "t2"}]},
    ],
    "limits": {"retries": 3, "secure": True},
}

AFTER = {
    "": {"~key/雪": "v2"},
    "modules": [
        {"id": "ui/主界面", "version": 3, "flag": 1,
         "deps": [{"id": "x"}, {"id": "a"}, {"id": "y", "pin": True}]},
        {"id": "core", "version": 2, "enabled": True,
         "deps": [{"id": "c"}, {"id": "a"}]},
        {"id": "new", "version": 0, "deps": []},
    ],
    "plugins~1": [
        {"id": "p/2", "tags": [{"id": "t2"}, {"id": "t1"}, {"id": "t3"}]},
        {"id": "core", "note": "id shared with /modules, scoped per array"},
    ],
    "limits": {"retries": 3, "secure": 1},
    "新增/段~": None,
}


def replay_stepwise(document, patch):
    """Apply one op at a time, returning every intermediate document."""
    states = [document]
    for op in patch:
        states.append(apply(states[-1], [op]))
    return states


class NestedDiffTest(unittest.TestCase):
    def test_forward_and_rollback_stepwise(self):
        forward = diff(BEFORE, AFTER)
        backward = diff(AFTER, BEFORE)
        self.assertEqual(replay_stepwise(BEFORE, forward)[-1], AFTER)
        self.assertEqual(replay_stepwise(AFTER, backward)[-1], BEFORE)
        self.assertEqual(apply(BEFORE, forward), AFTER)
        self.assertEqual(apply(AFTER, backward), BEFORE)

    def test_forward_patch_shape(self):
        patch = diff(BEFORE, AFTER)
        # bool -> int is a replace, never confused with equality
        self.assertIn({"op": "replace", "path": "/limits/secure", "value": 1}, patch)
        self.assertIn({"op": "replace", "path": "/modules/1/flag", "value": 1}, patch)
        # special key names are RFC 6901 escaped ("":/"", "~key/雪" inside)
        self.assertIn({"op": "replace", "path": "//~0key~1雪", "value": "v2"}, patch)
        self.assertIn({"op": "add", "path": "/新增~1段~0", "value": None}, patch)
        # surviving ids keep identity: the only element-level add/remove
        # pairs are for departed "old" and arrived "new"
        element_ops = [
            op for op in patch
            if op["op"] in ("add", "remove") and op["path"].count("/") == 2
        ]
        self.assertEqual(
            sorted((op["op"], op["path"]) for op in element_ops),
            [("add", "/modules/2"), ("remove", "/modules/2")],
        )
        add_op = next(op for op in element_ops if op["op"] == "add")
        self.assertEqual(add_op["value"], {"id": "new", "version": 0, "deps": []})
        # field edits of surviving ids recurse instead of replacing elements
        self.assertIn({"op": "replace", "path": "/modules/0/version", "value": 2}, patch)
        self.assertFalse(any(op["path"] == "/modules" for op in patch))

    def test_ids_are_scoped_per_array(self):
        before = {
            "a": [{"id": "core"}, {"id": "z"}],
            "b": [{"id": "core", "v": 1}],
        }
        after = {
            "a": [{"id": "z"}, {"id": "core"}],
            "b": [{"id": "core", "v": 1}],
        }
        patch = diff(before, after)
        self.assertEqual(len(patch), 1)
        self.assertEqual(patch[0]["op"], "move")
        self.assertTrue(patch[0]["path"].startswith("/a/"))
        self.assertEqual(apply(before, patch), after)


class HandwrittenMoveSemanticsTest(unittest.TestCase):
    """Pin down move semantics with patches written by hand, so diff and
    apply cannot merely vouch for each other."""

    def test_move_target_index_is_post_removal(self):
        doc = {"a": [{"id": "x"}, {"id": "y"}, {"id": "z"}, {"id": "w"}]}
        # remove "x" first -> [y, z, w]; insert at index 2 -> [y, z, x, w]
        patch = [{"op": "move", "from": "/a/0", "path": "/a/2"}]
        self.assertEqual(apply(doc, patch),
                         {"a": [{"id": "y"}, {"id": "z"}, {"id": "x"}, {"id": "w"}]})

    def test_move_to_end_uses_length_after_removal(self):
        doc = {"a": [{"id": "x"}, {"id": "y"}, {"id": "z"}]}
        patch = [{"op": "move", "from": "/a/0", "path": "/a/2"}]
        self.assertEqual(apply(doc, patch),
                         {"a": [{"id": "y"}, {"id": "z"}, {"id": "x"}]})

    def test_move_backward(self):
        doc = {"a": [{"id": "x"}, {"id": "y"}, {"id": "z"}]}
        patch = [{"op": "move", "from": "/a/2", "path": "/a/0"}]
        self.assertEqual(apply(doc, patch),
                         {"a": [{"id": "z"}, {"id": "x"}, {"id": "y"}]})

    def test_move_carries_element_content(self):
        doc = {"a": [{"id": "x", "v": 42}, {"id": "y"}]}
        patch = [{"op": "move", "from": "/a/0", "path": "/a/1"}]
        self.assertEqual(apply(doc, patch),
                         {"a": [{"id": "y"}, {"id": "x", "v": 42}]})

    def test_move_between_arrays_via_parent_paths(self):
        # diff() only emits moves within one array, but apply() follows
        # plain RFC 6902 and accepts any from/path pair.
        doc = {"a": [{"id": "x"}], "b": [{"id": "y"}]}
        patch = [{"op": "move", "from": "/a/0", "path": "/b/1"}]
        self.assertEqual(apply(doc, patch), {"a": [], "b": [{"id": "y"}, {"id": "x"}]})

    def test_handwritten_rollback_of_diff_patch(self):
        before = {"a": [{"id": i} for i in "abcd"]}
        forward = diff(before, {"a": [{"id": i} for i in "bcad"]})
        self.assertEqual(forward, [{"op": "move", "from": "/a/0", "path": "/a/2"}])
        rollback = [{"op": "move", "from": "/a/2", "path": "/a/0"}]
        self.assertEqual(apply(apply(before, forward), rollback), before)


if __name__ == "__main__":
    unittest.main()
