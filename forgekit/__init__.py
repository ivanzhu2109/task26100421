"""ForgeKit schema version diff library.

Public API:
    diff(before, after)  -> RFC 6902 patch
    apply(document, patch) -> new document
"""

from ._apply import PatchError, apply
from ._diff import diff

__all__ = ["diff", "apply", "PatchError"]
__version__ = "0.1.0"
