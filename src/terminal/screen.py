"""Screen rendering — diffing, clipping, frame output."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from terminal.measure import char_width, display_width


def clip_and_pad(line: str, cols: int) -> str:
    """Clip to cols visible characters and pad with spaces to exactly cols."""
    if "\033" not in line and line.isascii():
        n = len(line)
        return line[:cols] if n >= cols else line + " " * (cols - n)
    return _clip_pad_scan(line, cols)


def clip(line: str, max_width: int) -> str:
    """Clip a line to max_width visible characters, preserving ANSI escapes."""
    if "\033" not in line and line.isascii():
        return line[:max_width] if len(line) > max_width else line
    return _clip_scan(line, max_width)


def _ansi_end(line: str, pos: int) -> int:
    """If pos starts a CSI escape, return position after it. Else return pos."""
    if line[pos] != "\033":
        return pos
    n = len(line)
    if pos + 1 >= n or line[pos + 1] != "[":
        return pos
    end = pos + 2
    while end < n and line[end] != "m":
        end += 1
    return end + 1


def _clip_pad_scan(line: str, cols: int) -> str:
    visible = 0
    pos = 0
    while pos < len(line):
        end = _ansi_end(line, pos)
        if end != pos:
            pos = end
            continue
        visible += char_width(line[pos])
        if visible > cols:
            return line[:pos] + "\033[0m"
        pos += 1
    if visible < cols:
        return line + " " * (cols - visible)
    return line


def _clip_scan(line: str, max_width: int) -> str:
    visible = 0
    pos = 0
    while pos < len(line):
        end = _ansi_end(line, pos)
        if end != pos:
            pos = end
            continue
        visible += char_width(line[pos])
        if visible > max_width:
            return line[:pos] + "\033[0m"
        pos += 1
    return line


def pad(line: str, cols: int) -> str:
    """Pad a line with spaces to exactly cols visible characters."""
    gap = cols - display_width(line)
    if gap > 0:
        return line + " " * gap
    return line


class Screen:
    """Diff-based terminal screen writer."""

    def __init__(
        self,
        write: Callable[[bytes], object] = sys.stdout.buffer.write,
        flush: Callable[[], object] = sys.stdout.buffer.flush,
    ) -> None:
        self._write = write
        self._flush = flush
        self._screen: list[str] = []
        self._rows = 0
        self._cols = 0

    def invalidate(self) -> None:
        """Force a full redraw on next render."""
        self._screen = []

    def render(self, lines: list[str]) -> None:
        """Write a frame with diff-based update to minimize flicker."""
        size = os.get_terminal_size()
        rows: int = size.lines
        cols: int = size.columns
        resized = rows != self._rows or cols != self._cols
        n_content = min(len(lines), rows)
        frame = [clip_and_pad(line, cols) for line in lines[:n_content]]
        if resized or not self._screen:
            frame += [" " * cols] * (rows - len(frame))
        else:
            n_clear = max(0, len(self._screen) - n_content)
            frame += [" " * cols] * n_clear

        if resized or not self._screen:
            body = render_full(frame)
        else:
            body = render_diff(frame, self._screen)
        self._write(f"\033[?2026h{body}\033[?2026l".encode())
        self._flush()

        self._screen = frame
        self._rows = rows
        self._cols = cols


def render_full(frame: list[str]) -> str:
    return "\033[H" + "\n".join(frame)


def render_diff(frame: list[str], prev: list[str]) -> str:
    return "".join(
        f"\033[{i + 1};1H{line}"
        for i, line in enumerate(frame)
        if line != (prev[i] if i < len(prev) else "")
    )
