"""Minimal ForgeKit usage example: diff two versions, roll back."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forgekit import apply, diff

v1 = {
    "name": "forgekit-demo",
    "features": [
        {"id": "auth", "enabled": True},
        {"id": "cache", "enabled": False},
        {"id": "beta", "enabled": True},
    ],
}

v2 = {
    "name": "forgekit-demo",
    "features": [
        {"id": "cache", "enabled": True},          # toggled + moved
        {"id": "auth", "enabled": True},
        {"id": "metrics", "enabled": False},       # new
    ],
}

if __name__ == "__main__":
    forward = diff(v1, v2)
    print("forward patch:")
    print(json.dumps(forward, indent=2, ensure_ascii=False))

    assert apply(v1, forward) == v2

    rollback = diff(v2, v1)  # swap the arguments to go back
    assert apply(v2, rollback) == v1
    print("\nrollback patch:")
    print(json.dumps(rollback, indent=2, ensure_ascii=False))
    print("\nround-trip ok")
