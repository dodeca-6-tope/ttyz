"""Flex layout primitives for terminal UI."""

from __future__ import annotations

import os
from collections.abc import Sequence

from terminal.measure import display_width


class Flex:
    """Flex layout utilities — arrange content like CSS flexbox."""

    @staticmethod
    def wrap(chunks: Sequence[object], width: int | None = None, sep: str = " ") -> list[str]:
        """Wrap chunks into lines that fit within width, joining with separator.

        Chunks can be str or Text (anything with len() and str()).
        If width is None, uses the current terminal width.
        """
        if width is None:
            width = os.get_terminal_size().columns - 1
        return _wrap_chunks([str(c) for c in chunks], width, sep)


def _wrap_chunks(strs: list[str], width: int, sep: str) -> list[str]:
    sep_w = display_width(sep)
    lines: list[str] = []
    cur_parts: list[str] = []
    cur_w = 0
    for s in strs:
        s_w = display_width(s)
        needed = s_w if not cur_parts else cur_w + sep_w + s_w
        if needed > width and cur_parts:
            lines.append(sep.join(cur_parts))
            cur_parts = []
            cur_w = 0
        cur_parts.append(s)
        cur_w = cur_w + sep_w + s_w if cur_w else s_w
    if cur_parts:
        lines.append(sep.join(cur_parts))
    return lines
