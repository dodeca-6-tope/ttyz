"""Display-width measurement — ANSI-aware, wide-char-aware."""

import re

from wcwidth import wcswidth

ANSI_RE = re.compile(r"\033\[[^m]*m")


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def display_width(s: str) -> int:
    stripped = strip_ansi(s)
    w = wcswidth(stripped)
    return w if w >= 0 else len(stripped)
