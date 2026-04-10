"""Screen rendering — clipping utilities and cell-based frame output."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from terminal.buffer import Buffer, parse_line
from terminal.buffer import render_diff as _buf_diff
from terminal.buffer import render_full as _buf_full
from terminal.measure import char_width, display_width


def clip_and_pad(line: str, width: int) -> str:
    """Clip to width visible characters and pad with spaces to exactly width."""
    if "\033" not in line and line.isascii():
        n = len(line)
        return line[:width] if n >= width else line + " " * (width - n)
    return _clip_scan(line, width, pad_to=True)


def clip(line: str, width: int) -> str:
    """Clip a line to width visible characters, preserving ANSI escapes."""
    if "\033" not in line and line.isascii():
        return line[:width]
    return _clip_scan(line, width)


def _ansi_end(line: str, pos: int) -> int:
    """If pos starts a CSI escape, return position after it. Else return pos."""
    if line[pos] != "\033":
        return pos
    n = len(line)
    if pos + 1 >= n or line[pos + 1] != "[":
        return pos
    end = pos + 2
    while end < n and not ("\x40" <= line[end] <= "\x7e"):
        end += 1
    return end + 1 if end < n else pos


def _clip_scan(line: str, width: int, *, pad_to: bool = False) -> str:
    visible = 0
    pos = 0
    while pos < len(line):
        end = _ansi_end(line, pos)
        if end != pos:
            pos = end
            continue
        visible += char_width(line[pos])
        if visible > width:
            return line[:pos] + "\033[0m"
        pos += 1
    if pad_to and visible < width:
        return line + " " * (width - visible)
    return line


def pad(line: str, width: int) -> str:
    """Pad a line with spaces to exactly width visible characters."""
    gap = width - display_width(line)
    if gap > 0:
        return line + " " * gap
    return line


class Screen:
    """Cell-based terminal screen writer with cell-level diffing."""

    def __init__(
        self,
        write: Callable[[bytes], object] = sys.stdout.buffer.write,
        flush: Callable[[], object] = sys.stdout.buffer.flush,
    ) -> None:
        self._write = write
        self._flush = flush
        self._prev: Buffer | None = None
        self._rows = 0
        self._cols = 0

    def invalidate(self) -> None:
        """Force a full redraw on next render."""
        self._prev = None

    def render(self, lines: list[str]) -> None:
        """Write a frame with cell-level diffing to minimize output."""
        size = os.get_terminal_size()
        rows: int = size.lines
        cols: int = size.columns
        full = rows != self._rows or cols != self._cols or self._prev is None

        buf = Buffer(cols, rows)
        for i, line in enumerate(lines[: min(len(lines), rows)]):
            parse_line(buf, i, line)

        if full or self._prev is None:
            body = _buf_full(buf)
        else:
            body = _buf_diff(buf, self._prev)

        self._write(f"\033[?2026h{body}\033[?2026l".encode())
        self._flush()

        self._prev = buf
        self._rows = rows
        self._cols = cols
