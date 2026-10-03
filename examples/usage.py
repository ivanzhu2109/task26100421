"""Minimal ForgeKit diff/apply example.  Run: python3 examples/usage.py"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forgekit import apply, diff

v1 = {
    "name": "shop-service",
    "replicas": 2,
    "debug": False,
    "routes": [
        {"id": "auth", "weight": 50},
        {"id": "cart", "weight": 30},
        {"id": "pay", "weight": 20},
    ],
}

v2 = {
    "name": "shop-service",
    "replicas": 3,
    "debug": 0,  # bool -> int: a real type change
    "routes": [
        {"id": "pay", "weight": 20},
        {"id": "auth", "weight": 80},  # edited in place, keeps identity
        {"id": "search", "weight": 10},  # new element
    ],
}

forward = diff(v1, v2)
rollback = diff(v2, v1)

print("forward patch:")
print(json.dumps(forward, indent=2, ensure_ascii=False))

assert apply(v1, forward) == v2
assert apply(v2, rollback) == v1
print("\napply(v1, forward) == v2 and apply(v2, rollback) == v1")
