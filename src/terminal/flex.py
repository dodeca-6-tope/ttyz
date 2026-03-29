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
    line: list[str] = []
    line_w = 0
    for s in strs:
        s_w = display_width(s)
        needed = line_w + sep_w + s_w if line else s_w
        if needed > width and line:
            lines.append(sep.join(line))
            line, line_w = [s], s_w
            continue
        line.append(s)
        line_w = needed
    if line:
        lines.append(sep.join(line))
    return lines
