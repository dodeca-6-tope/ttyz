"""Low-level terminal: alt screen, raw mode, input, rendering."""

import atexit
import codecs
import os
from dataclasses import dataclass
import select
import sys
import termios
import tty


@dataclass(frozen=True)
class Paste:
    """Represents pasted text from bracketed paste."""
    text: str

    def __str__(self) -> str:
        return self.text


class Terminal:
    """Context manager for full-screen terminal UI sessions."""

    def __init__(self):
        self._fd = None
        self._saved = None
        self._active = False
        self._atexit = False
        self._utf8 = codecs.getincrementaldecoder("utf-8")("ignore")

    @property
    def active(self) -> bool:
        return self._active

    def __enter__(self):
        self._fd = sys.stdin.fileno()
        self._saved = termios.tcgetattr(self._fd)
        self._enter_raw()
        self._active = True
        # Alt screen, hide cursor, bracketed paste, focus events
        sys.stdout.write("\033[?1049h\033[?25l\033[?2004h\033[?1004h")
        sys.stdout.flush()
        if not self._atexit:
            atexit.register(self.cleanup)
            self._atexit = True
        return self

    def __exit__(self, *_):
        self.cleanup()

    def cleanup(self):
        """Leave alt screen, show cursor, restore terminal."""
        if not self._active:
            return
        self._active = False
        sys.stdout.write("\033[?1004l\033[?2004l\033[?25h\033[?1049l")
        sys.stdout.flush()
        self._restore()

    def suspend(self):
        """Leave alt screen and restore terminal for a child process."""
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()
        self._restore()

    def resume(self):
        """Re-enter alt screen and raw mode after a child process."""
        self._enter_raw()
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()

    def readkey(self) -> str | Paste | None:
        """Read a single keypress. Returns None on timeout (1/60s)."""
        if not select.select([self._fd], [], [], 1 / 60)[0]:
            return None
        ch = os.read(self._fd, 1)
        if ch == b"\x1b":
            if select.select([self._fd], [], [], 0.02)[0]:
                seq = os.read(self._fd, 16)
                # Bracketed paste: \x1b[200~ ... \x1b[201~
                if seq.startswith(b"[200~"):
                    return self._read_paste(seq[5:])
                if seq[:2] == b"[A": return "up"
                if seq[:2] == b"[B": return "down"
                if seq[:2] == b"[C": return "right"
                if seq[:2] == b"[D": return "left"
                if seq[:2] == b"[H": return "home"
                if seq[:2] == b"[F": return "end"
                if seq[:2] == b"[Z": return "shift-tab"
                if seq[:2] == b"[I": return "focus"
                if seq[:2] == b"[O": return None  # focus lost
                if seq == b"[3~": return "delete"
                if seq[:1] == b"[" and len(seq) >= 5 and seq[1:2] == b"1":
                    mod, d = seq[3:4], seq[4:5]
                    # mod 3 = Option, mod 9 = Cmd (iTerm2)
                    if mod in (b"3", b"9"):
                        if d == b"C": return "word-right"
                        if d == b"D": return "word-left"
                    if mod == b"2":  # Shift
                        if d == b"C": return "end"
                        if d == b"D": return "home"
                # Double escape: \x1b\x1b[X — Option+arrow on some terminals
                if seq[:1] == b"\x1b" and len(seq) >= 3:
                    if seq[1:3] == b"[C": return "word-right"
                    if seq[1:3] == b"[D": return "word-left"
                    if seq[1:3] == b"[A": return "up"
                    if seq[1:3] == b"[B": return "down"
                if seq[:1] == b"[":
                    return None  # ignore unknown CSI sequences
                if seq[:1] == b"\x7f": return "delete-word"
                if seq[:1] == b"b": return "word-left"
                if seq[:1] == b"f": return "word-right"
                if seq[:1] == b"d": return "delete-word"
                return None  # ignore unknown escape sequences
            return "esc"
        if ch == b"\t": return "tab"
        if ch in (b"\r", b"\n"): return "enter"
        if ch == b"\x01": return "ctrl-a"
        if ch == b"\x02": return "ctrl-b"
        if ch == b"\x03": raise KeyboardInterrupt
        if ch == b"\x04": return "ctrl-d"
        if ch == b"\x05": return "ctrl-e"
        if ch == b"\x06": return "ctrl-f"
        if ch == b"\x07": return "ctrl-g"
        if ch == b"\x0b": return "ctrl-k"
        if ch == b"\x0c": return "ctrl-l"
        if ch == b"\x0e": return "ctrl-n"
        if ch == b"\x0f": return "ctrl-o"
        if ch == b"\x10": return "ctrl-p"
        if ch == b"\x11": return "ctrl-q"
        if ch == b"\x12": return "ctrl-r"
        if ch == b"\x14": return "ctrl-t"
        if ch == b"\x15": return "clear-line"
        if ch == b"\x16": return "ctrl-v"
        if ch == b"\x17": return "delete-word"
        if ch == b"\x18": return "ctrl-x"
        if ch == b"\x19": return "ctrl-y"
        if ch == b"\x1a": return "ctrl-z"
        if ch == b" ": return "space"
        if ch in (b"\x7f", b"\x08"): return "backspace"
        result = self._utf8.decode(ch)
        while not result:
            if not select.select([self._fd], [], [], 0.01)[0]:
                self._utf8.reset()
                return None
            result = self._utf8.decode(os.read(self._fd, 1))
        return result

    def _read_paste(self, initial: bytes) -> Paste:
        """Read bracketed paste content until \\x1b[201~."""
        buf = bytearray(initial)
        end = b"\x1b[201~"
        while True:
            if end in buf:
                idx = buf.index(end)
                return Paste(buf[:idx].decode("utf-8", errors="replace").replace("\r", "\n"))
            if select.select([self._fd], [], [], 0.1)[0]:
                buf.extend(os.read(self._fd, 4096))
            else:
                return Paste(buf.decode("utf-8", errors="replace").replace("\r", "\n"))

    def render(self, lines: list[str]):
        """Write full screen with synchronized update to avoid flicker."""
        parts = ["\033[?2026h\033[H"]
        for line in lines:
            parts.append(line)
            parts.append("\033[K\n")
        parts.append("\033[J\033[?2026l")
        sys.stdout.buffer.write("".join(parts).encode())
        sys.stdout.buffer.flush()

    def _enter_raw(self):
        """Switch to raw mode, re-enable output processing for \\n → \\r\\n."""
        tty.setraw(self._fd)
        attrs = termios.tcgetattr(self._fd)
        attrs[1] |= termios.OPOST
        termios.tcsetattr(self._fd, termios.TCSADRAIN, attrs)

    def _restore(self):
        """Restore saved terminal attributes."""
        if self._saved:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
