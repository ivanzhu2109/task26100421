"""ForgeKit schema version diff library.

Computes RFC 6902 JSON Patches between two immutable, already-parsed JSON
documents and replays them.  Neither ``diff`` nor ``apply`` mutates its
inputs.
"""

from forgekit.differ import diff
from forgekit.applier import apply

__all__ = ["diff", "apply"]
