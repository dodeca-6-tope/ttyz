"""Low-level terminal: alt screen, raw mode, input, rendering."""

from __future__ import annotations

import atexit
import codecs
import os
import select
import signal
import sys
import termios
import tty
from collections.abc import Callable
from dataclasses import dataclass
from types import FrameType
from typing import Any


@dataclass(frozen=True)
class Paste:
    """Represents pasted text from bracketed paste."""
    text: str

    def __str__(self) -> str:
        return self.text


# Single-byte → key name
_BYTE_KEYS: dict[bytes, str] = {
    b"\t": "tab",
    b"\r": "enter",
    b"\n": "enter",
    b"\x01": "ctrl-a",
    b"\x02": "ctrl-b",
    b"\x04": "ctrl-d",
    b"\x05": "ctrl-e",
    b"\x06": "ctrl-f",
    b"\x07": "ctrl-g",
    b"\x0b": "ctrl-k",
    b"\x0c": "ctrl-l",
    b"\x0e": "ctrl-n",
    b"\x0f": "ctrl-o",
    b"\x10": "ctrl-p",
    b"\x11": "ctrl-q",
    b"\x12": "ctrl-r",
    b"\x14": "ctrl-t",
    b"\x15": "clear-line",
    b"\x16": "ctrl-v",
    b"\x17": "delete-word",
    b"\x18": "ctrl-x",
    b"\x19": "ctrl-y",
    b"\x1a": "ctrl-z",
    b" ": "space",
    b"\x7f": "backspace",
    b"\x08": "backspace",
}

# \x1b[ + 1-2 bytes → key name  (CSI sequences)
_CSI_KEYS: dict[bytes, str] = {
    b"A": "up",
    b"B": "down",
    b"C": "right",
    b"D": "left",
    b"H": "home",
    b"F": "end",
    b"Z": "shift-tab",
    b"I": "focus",
    b"3~": "delete",
}

# \x1b + single byte → key name  (Alt / Option sequences)
_ESC_KEYS: dict[bytes, str] = {
    b"\x7f": "delete-word",
    b"b": "word-left",
    b"f": "word-right",
    b"d": "delete-word",
}

# \x1b[1;{mod}{dir} → key name  (modifier arrow sequences)
_MOD_KEYS: dict[tuple[bytes, bytes], str] = {
    (b"3", b"C"): "word-right",   # Option
    (b"3", b"D"): "word-left",
    (b"9", b"C"): "word-right",   # Cmd (iTerm2)
    (b"9", b"D"): "word-left",
    (b"2", b"C"): "end",          # Shift
    (b"2", b"D"): "home",
}


class Terminal:
    """Context manager for full-screen terminal UI sessions."""

    def __init__(self) -> None:
        self._fd: int | None = None
        self._saved: list[Any] | None = None
        self._active = False
        self._atexit = False
        self._utf8 = codecs.getincrementaldecoder("utf-8")("ignore")
        self._resized = False
        self._prev_sigwinch: Callable[[int, FrameType | None], Any] | int | None = None
        self._screen: list[str] = []  # what's currently on the terminal
        self._screen_rows = 0
        self._screen_cols = 0

    @property
    def active(self) -> bool:
        return self._active

    def __enter__(self) -> Terminal:
        fd = sys.stdin.fileno()
        self._fd = fd
        self._saved = termios.tcgetattr(fd)
        self._enter_raw()
        self._active = True
        # Alt screen, hide cursor, bracketed paste, focus events
        sys.stdout.write("\033[?1049h\033[?25l\033[?2004h\033[?1004h")
        sys.stdout.flush()
        self._prev_sigwinch = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self._on_sigwinch)
        if not self._atexit:
            atexit.register(self.cleanup)
            self._atexit = True
        return self

    def __exit__(self, *_: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Leave alt screen, show cursor, restore terminal."""
        if not self._active:
            return
        self._active = False
        self._screen = []
        sys.stdout.write("\033[?1004l\033[?2004l\033[?25h\033[?1049l")
        sys.stdout.flush()
        self._restore()
        if self._prev_sigwinch is not None:
            signal.signal(signal.SIGWINCH, self._prev_sigwinch)
            self._prev_sigwinch = None

    def _on_sigwinch(self, signum: int, frame: FrameType | None) -> None:
        self._resized = True
        self._screen = []  # invalidate — terminal reflowed content

    def suspend(self) -> None:
        """Leave alt screen and restore terminal for a child process."""
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()
        self._restore()

    def resume(self) -> None:
        """Re-enter alt screen and raw mode after a child process."""
        self._enter_raw()
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()
        self._screen = []  # force full redraw on next render

    def readkey(self) -> str | Paste | None:
        """Read a single keypress. Returns None on timeout (1/60s) or resize."""
        assert self._fd is not None
        fd = self._fd
        if self._resized:
            self._resized = False
            return "resize"
        try:
            ready = select.select([fd], [], [], 1 / 60)[0]
        except InterruptedError:
            if self._resized:
                self._resized = False
                return "resize"
            return None
        if not ready:
            return None
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            return self._read_escape(fd)
        if ch == b"\x03": raise KeyboardInterrupt
        hit = _BYTE_KEYS.get(ch)
        if hit:
            return hit
        result = self._utf8.decode(ch)
        while not result:
            if not select.select([fd], [], [], 0.01)[0]:
                self._utf8.reset()
                return None
            result = self._utf8.decode(os.read(fd, 1))
        return result

    def _read_escape(self, fd: int) -> str | Paste | None:
        """Parse an escape sequence into a key name."""
        if not select.select([fd], [], [], 0.02)[0]:
            return "esc"
        seq = os.read(fd, 16)
        # Bracketed paste
        if seq.startswith(b"[200~"):
            return self._read_paste(seq[5:])
        # CSI sequence: \x1b[...
        if seq[:1] == b"[":
            return self._parse_csi(seq[1:])
        # Double escape: \x1b\x1b[X — Option+arrow on some terminals
        if seq[:1] == b"\x1b" and len(seq) >= 3:
            return _CSI_KEYS.get(seq[2:3])
        # Alt/Option + key
        return _ESC_KEYS.get(seq[:1])

    @staticmethod
    def _parse_csi(csi: bytes) -> str | None:
        """Parse a CSI (Control Sequence Introducer) payload."""
        if csi[:1] == b"O":
            return None  # focus lost
        hit = _CSI_KEYS.get(csi) or _CSI_KEYS.get(csi[:2])
        if hit:
            return hit
        # Modifier: 1;{mod}{dir}
        if len(csi) >= 4 and csi[:1] == b"1":
            return _MOD_KEYS.get((csi[2:3], csi[3:4]))
        return None

    def _read_paste(self, initial: bytes) -> Paste:
        """Read bracketed paste content until \\x1b[201~."""
        assert self._fd is not None
        fd = self._fd
        buf = bytearray(initial)
        end = b"\x1b[201~"
        while True:
            if end in buf:
                idx = buf.index(end)
                return Paste(buf[:idx].decode("utf-8", errors="replace").replace("\r", "\n"))
            if select.select([fd], [], [], 0.1)[0]:
                buf.extend(os.read(fd, 4096))
            else:
                return Paste(buf.decode("utf-8", errors="replace").replace("\r", "\n"))

    def render(self, lines: list[str]) -> None:
        """Write full screen with diff-based update to minimize flicker."""
        size = os.get_terminal_size()
        rows, cols = size.lines, size.columns
        resized = rows != self._screen_rows or cols != self._screen_cols

        frame = list(lines[:rows]) + [""] * max(0, rows - len(lines))

        parts = ["\033[?2026h"]
        if resized or not self._screen:
            parts.append("\033[H" + "\033[K\n".join(frame) + "\033[K")
        else:
            for i in range(rows):
                old = self._screen[i] if i < len(self._screen) else ""
                if frame[i] != old:
                    parts.append(f"\033[{i + 1};1H{frame[i]}\033[K")
        parts.append("\033[?2026l")

        sys.stdout.buffer.write("".join(parts).encode())
        sys.stdout.buffer.flush()

        self._screen = frame
        self._screen_rows = rows
        self._screen_cols = cols

    def _enter_raw(self) -> None:
        """Switch to raw mode, re-enable output processing for \\n → \\r\\n."""
        assert self._fd is not None
        tty.setraw(self._fd)
        attrs = termios.tcgetattr(self._fd)
        attrs[1] |= termios.OPOST
        termios.tcsetattr(self._fd, termios.TCSADRAIN, attrs)

    def _restore(self) -> None:
        """Restore saved terminal attributes."""
        if self._saved and self._fd is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
