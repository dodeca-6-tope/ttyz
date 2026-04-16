"""Terminal — TTY lifecycle that composes Screen and KeyReader."""

from __future__ import annotations

import atexit
import contextlib
import os
import select as _select
import signal
import sys
import termios
import tty
from collections.abc import Callable
from types import FrameType
from typing import Any

from ttyz.control import Command
from ttyz.ext import Buffer, render_to_buffer
from ttyz.keys import (
    KITTY_DISABLE,
    KITTY_ENABLE,
    KITTY_QUERY,
    Event,
    KeyReader,
    Resize,
)


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
        self._rows: int = 0
        self._cols: int = 0

    def invalidate(self) -> None:
        """Force a full redraw on next render."""
        self._prev = None

    def render(self, node: object) -> None:
        """Render a node tree to the terminal with cell-level diffing."""
        size = os.get_terminal_size()
        rows: int = size.lines
        cols: int = size.columns
        prev = self._prev

        buf = Buffer(cols, rows)
        render_to_buffer(node, buf)

        if prev is None or (rows, cols) != (self._rows, self._cols):
            body = buf.dump()
        else:
            body = buf.diff(prev)

        self._write(f"\033[?2026h{body}\033[?2026l".encode())
        self._flush()

        self._prev = buf
        self._rows = rows
        self._cols = cols


_ENTER = "\033[?1049h\033[?25l\033[?7l\033[?2004h\033[?1004h\033[?1000h\033[?1006h"
_EXIT = "\033[?1006l\033[?1000l\033[?1004l\033[?2004l\033[?7h\033[?25h\033[?1049l"


class TTY:
    """Context manager for full-screen terminal UI sessions."""

    def __init__(self, screen: Screen | None = None) -> None:
        self._fd: int | None = None
        self._saved: list[Any] | None = None
        self._active = False
        self._resized = False
        self._kitty = False
        self._prev_sigwinch: Callable[[int, FrameType | None], Any] | int | None = None
        self._keys: KeyReader | None = None
        self._screen = screen or Screen()
        self._wake_r, self._wake_w = os.pipe()
        atexit.register(self.cleanup)

    def __enter__(self) -> TTY:
        fd = sys.stdin.fileno()
        self._fd = fd
        self._saved = termios.tcgetattr(fd)
        self._enter_raw()
        self._active = True
        self._prev_sigwinch = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self._on_sigwinch)
        self._keys = KeyReader(fd, self._wake_r)
        return self

    def __exit__(self, *_: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Leave alt screen, show cursor, restore terminal."""
        if self._active:
            self._active = False
            self._screen.invalidate()
            if self._kitty:
                sys.stdout.write(KITTY_DISABLE)
                self._kitty = False
            sys.stdout.write(_EXIT)
            sys.stdout.flush()
            if self._saved and self._fd is not None:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
            if self._prev_sigwinch is not None:
                signal.signal(signal.SIGWINCH, self._prev_sigwinch)
                self._prev_sigwinch = None
        atexit.unregister(self.cleanup)
        if self._wake_r >= 0:
            os.close(self._wake_r)
            os.close(self._wake_w)
            self._wake_r = -1
            self._wake_w = -1

    def _on_sigwinch(self, signum: int, frame: FrameType | None) -> None:
        self._resized = True
        self._screen.invalidate()

    def readkey(self, timeout: float = 1 / 60) -> Event | None:
        """Read a single input event. Returns None on timeout."""
        assert self._keys is not None
        if self._resized:
            self._resized = False
            size = os.get_terminal_size()
            return Resize(cols=size.columns, lines=size.lines)
        result = self._keys.read(timeout)
        if result is None and self._resized:
            self._resized = False
            size = os.get_terminal_size()
            return Resize(cols=size.columns, lines=size.lines)
        return result

    def draw(self, node: object) -> None:
        """Draw a node tree to the terminal."""
        self._screen.render(node)

    def write(self, *commands: Command) -> None:
        """Write control commands to the terminal.

        tty.write(SetTitle("my app"), CursorShape(2))
        """
        sys.stdout.write("".join(c.sequence() for c in commands))
        sys.stdout.flush()

    @property
    def size(self) -> os.terminal_size:
        """Current terminal dimensions (columns, lines)."""
        return os.get_terminal_size()

    def wake(self) -> None:
        """Wake the event loop from any thread."""
        with contextlib.suppress(OSError):
            os.write(self._wake_w, b"\x00")

    @property
    def active(self) -> bool:
        return self._active

    def suspend(self) -> None:
        """Leave alt screen and restore terminal for a child process."""
        if self._kitty:
            sys.stdout.write(KITTY_DISABLE)
        sys.stdout.write(_EXIT)
        sys.stdout.flush()
        if self._saved and self._fd is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def resume(self) -> None:
        """Re-enter alt screen and raw mode after a child process."""
        self._enter_raw()
        if self._kitty:
            sys.stdout.write(KITTY_ENABLE)
            sys.stdout.flush()
        self._screen.invalidate()

    def kitty_supported(self) -> bool:
        """Check if terminal supports Kitty keyboard protocol."""
        if self._fd is None:
            return False
        sys.stdout.write(KITTY_QUERY)
        sys.stdout.flush()
        ready = _select.select([self._fd], [], [], 0.01)[0]
        if not ready:
            return False
        buf = os.read(self._fd, 256)
        idx = buf.find(b"\x1b[?")
        if idx < 0:
            return False
        for i in range(idx + 3, len(buf)):
            if buf[i] == ord("u"):
                return True
            if not (0x30 <= buf[i] <= 0x3F):
                break
        return False

    def kitty_enable(self) -> None:
        """Enable Kitty keyboard protocol. Keys will include modifier info."""
        self._kitty = True
        sys.stdout.write(KITTY_ENABLE)
        sys.stdout.flush()

    def kitty_disable(self) -> None:
        """Disable Kitty keyboard protocol."""
        self._kitty = False
        sys.stdout.write(KITTY_DISABLE)
        sys.stdout.flush()

    def _enter_raw(self) -> None:
        """Switch to raw mode with output processing, enter alt screen."""
        assert self._fd is not None
        tty.setraw(self._fd)
        attrs = termios.tcgetattr(self._fd)
        attrs[1] |= termios.OPOST
        termios.tcsetattr(self._fd, termios.TCSADRAIN, attrs)
        sys.stdout.write(_ENTER)
        sys.stdout.flush()
