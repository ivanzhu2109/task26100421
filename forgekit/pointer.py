"""RFC 6901 JSON Pointer helpers (escape/unescape/parse/build)."""

from typing import List


def escape_token(token: str) -> str:
    """Escape a single reference token per RFC 6901."""
    return token.replace("~", "~0").replace("/", "~1")


def unescape_token(token: str) -> str:
    """Unescape a single reference token per RFC 6901."""
    return token.replace("~1", "/").replace("~0", "~")


def build_pointer(tokens: List[str]) -> str:
    """Build a JSON Pointer string from reference tokens."""
    return "".join("/" + escape_token(token) for token in tokens)


def parse_pointer(pointer: str) -> List[str]:
    """Parse a JSON Pointer string into reference tokens."""
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer!r}")
    return [unescape_token(part) for part in pointer.split("/")[1:]]
