"""Terminal — TTY lifecycle that composes Screen and KeyReader."""

from __future__ import annotations

import atexit
import contextlib
import os
import signal
import sys
import termios
import tty
from collections.abc import Callable
from types import FrameType
from typing import Any

from terminal.keys import KeyReader, Paste
from terminal.screen import Screen

_ENTER = "\033[?1049h\033[?25l\033[?7l\033[?2004h\033[?1004h\033[?1000h\033[?1006h"
_EXIT = "\033[?1006l\033[?1000l\033[?1004l\033[?2004l\033[?7h\033[?25h\033[?1049l"


class TTY:
    """Context manager for full-screen terminal UI sessions."""

    def __init__(self) -> None:
        self._fd: int | None = None
        self._saved: list[Any] | None = None
        self._active = False
        self._resized = False
        self._prev_sigwinch: Callable[[int, FrameType | None], Any] | int | None = None
        self._keys: KeyReader | None = None
        self.screen = Screen()
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
        if not self._active:
            return
        self._active = False
        self.screen.invalidate()
        sys.stdout.write(_EXIT)
        sys.stdout.flush()
        if self._saved and self._fd is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        if self._prev_sigwinch is not None:
            signal.signal(signal.SIGWINCH, self._prev_sigwinch)
            self._prev_sigwinch = None
        os.close(self._wake_r)
        os.close(self._wake_w)

    def _on_sigwinch(self, signum: int, frame: FrameType | None) -> None:
        self._resized = True
        self.screen.invalidate()

    def readkey(self, timeout: float = 1 / 60) -> str | Paste | None:
        """Read a single keypress. Returns 'resize' on terminal resize, None on timeout."""
        assert self._keys is not None
        if self._resized:
            self._resized = False
            return "resize"
        result = self._keys.read(timeout)
        if result is None and self._resized:
            self._resized = False
            return "resize"
        return result

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
        sys.stdout.write(_EXIT)
        sys.stdout.flush()
        if self._saved and self._fd is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def resume(self) -> None:
        """Re-enter alt screen and raw mode after a child process."""
        self._enter_raw()
        self.screen.invalidate()

    def _enter_raw(self) -> None:
        """Switch to raw mode with output processing, enter alt screen."""
        assert self._fd is not None
        tty.setraw(self._fd)
        attrs = termios.tcgetattr(self._fd)
        attrs[1] |= termios.OPOST
        termios.tcsetattr(self._fd, termios.TCSADRAIN, attrs)
        sys.stdout.write(_ENTER)
        sys.stdout.flush()
