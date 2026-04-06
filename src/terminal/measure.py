"""Display-width measurement — ANSI-aware, wide-char-aware."""

import re

from wcwidth import wcwidth

ANSI_RE = re.compile(r"\033\[[^m]*m")


def strip_ansi(s: str) -> str:
    if "\033" not in s:
        return s
    return ANSI_RE.sub("", s)


def char_width(ch: str) -> int:
    """Display width of a single character."""
    w = wcwidth(ch)
    return w if w >= 0 else 0


def display_width(s: str) -> int:
    if "\033" not in s:
        return len(s) if s.isascii() else _width_plain(s)
    return _width_plain(ANSI_RE.sub("", s))


def _width_plain(s: str) -> int:
    """Width of a string with no ANSI codes — single-pass wcwidth."""
    w = 0
    for ch in s:
        cw = wcwidth(ch)
        if cw > 0:
            w += cw
    return w


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
