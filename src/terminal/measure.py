"""Display-width measurement — ANSI-aware, wide-char-aware."""

import re
from functools import lru_cache

from terminal.buffer import c_display_width, char_width  # noqa: F401 — re-exported

ANSI_RE = re.compile(r"\033\[[^@-~]*[@-~]")

_cached = lru_cache(maxsize=4096)(c_display_width)


def display_width(s: str) -> int:
    if len(s) < 512:
        return _cached(s)
    return c_display_width(s)


def strip_ansi(s: str) -> str:
    if "\033" not in s:
        return s
    return ANSI_RE.sub("", s)


def distribute(total: int, weights: list[int]) -> list[int]:
    """Distribute total proportionally among weighted slots."""
    if not weights:
        return []
    total_weight = sum(weights)
    cum_weight = 0
    cum_space = 0
    sizes: list[int] = []
    for w in weights:
        cum_weight += w
        target = total * cum_weight // total_weight
        sizes.append(target - cum_space)
        cum_space = target
    return sizes


def slice_at_width(s: str, max_width: int) -> str:
    """Slice a plain string to fit within max_width display columns."""
    if s.isascii():
        return s[:max_width]
    w = 0
    for i, ch in enumerate(s):
        cw = char_width(ch)
        if w + cw > max_width:
            return s[:i]
        w += cw
    return s
