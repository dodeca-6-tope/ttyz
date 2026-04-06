"""Key maps and escape sequence classification."""

from __future__ import annotations

import codecs
import os
import select
from dataclasses import dataclass


@dataclass(frozen=True)
class Paste:
    """Represents pasted text from bracketed paste."""

    text: str


# Single-byte → key name
BYTE_KEYS: dict[bytes, str] = {
    b"\t": "tab",
    b"\r": "enter",
    b"\n": "enter",
    b"\x01": "home",
    b"\x02": "ctrl-b",
    b"\x04": "ctrl-d",
    b"\x05": "end",
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
CSI_KEYS: dict[bytes, str] = {
    b"A": "up",
    b"B": "down",
    b"C": "right",
    b"D": "left",
    b"H": "home",
    b"F": "end",
    b"Z": "shift-tab",
    b"I": "focus",
    b"3~": "delete",
    b"5~": "page-up",
    b"6~": "page-down",
}

# \x1b + single byte → key name  (Alt / Option sequences)
ESC_KEYS: dict[bytes, str] = {
    b"\x7f": "delete-word",
    b"b": "word-left",
    b"f": "word-right",
    b"d": "delete-word",
}

# \x1b\x1b[X → key name  (double-escape Option+arrow on some terminals)
DBL_ESC_KEYS: dict[bytes, str] = {
    b"C": "word-right",
    b"D": "word-left",
    b"A": "up",
    b"B": "down",
}

# \x1b[1;{mod}{dir} → key name  (modifier arrow sequences)
MOD_KEYS: dict[tuple[bytes, bytes], str] = {
    (b"3", b"C"): "word-right",  # Option
    (b"3", b"D"): "word-left",
    (b"9", b"C"): "word-right",  # Cmd (iTerm2)
    (b"9", b"D"): "word-left",
    (b"2", b"C"): "end",  # Shift
    (b"2", b"D"): "home",
}


class KeyReader:
    """Reads and classifies terminal input from a file descriptor."""

    def __init__(self, fd: int, wake_fd: int | None = None) -> None:
        self._fd = fd
        self._wake_fd = wake_fd
        self._utf8 = codecs.getincrementaldecoder("utf-8")("ignore")
        self._buf = bytearray()

    def _fill(self, timeout: float) -> bool:
        """Wait up to timeout for data, then drain all available bytes into _buf."""
        if self._buf:
            return True
        fds = [self._fd] if self._wake_fd is None else [self._fd, self._wake_fd]
        try:
            ready = select.select(fds, [], [], timeout)[0]
        except InterruptedError:
            return False
        if self._wake_fd is not None and self._wake_fd in ready:
            os.read(self._wake_fd, 1024)
        if self._fd in ready:
            self._buf.extend(os.read(self._fd, 4096))
        return bool(self._buf)

    def _consume(self, n: int = 1) -> bytes:
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    def read(self, timeout: float = 1 / 60) -> str | Paste | None:
        """Read a single keypress. Returns None on timeout or wake."""
        if not self._fill(timeout):
            return None
        return self._classify()

    def _classify(self) -> str | Paste | None:
        ch = self._consume()
        if ch == b"\x1b":
            return self._read_escape()
        if ch == b"\x03":
            raise KeyboardInterrupt
        return BYTE_KEYS.get(ch) or self._read_utf8(ch)

    def _read_utf8(self, initial: bytes) -> str | None:
        result = self._utf8.decode(initial)
        while not result:
            if not self._fill(0.01):
                self._utf8.reset()
                return None
            result = self._utf8.decode(self._consume())
        return result

    def _read_escape(self) -> str | Paste | None:
        """Parse an escape sequence from the buffer."""
        if not self._fill(0.004):
            return "esc"
        # Bracketed paste
        if self._buf.startswith(b"[200~"):
            del self._buf[:5]
            return self._read_paste()
        # CSI sequence: \x1b[...
        if self._buf.startswith(b"["):
            del self._buf[:1]
            return self._read_csi()
        # Double escape: \x1b\x1b[X — Option+arrow on some terminals
        if self._buf.startswith(b"\x1b[") and len(self._buf) >= 3:
            del self._buf[:2]
            return DBL_ESC_KEYS.get(self._consume())
        # Alt/Option + key
        return ESC_KEYS.get(self._consume())

    def _csi_end(self) -> int | None:
        """Find the index of the CSI terminator byte (0x40–0x7E), or None."""
        for i in range(len(self._buf)):
            if 0x40 <= self._buf[i] <= 0x7E:
                return i
        return None

    def _read_csi(self) -> str | None:
        """Read a complete CSI sequence from the buffer and parse it."""
        end = self._csi_end()
        if end is None and self._fill(0.004):
            end = self._csi_end()
        return parse_csi(
            self._consume((end + 1) if end is not None else len(self._buf))
        )

    def _read_paste(self) -> Paste:
        """Read bracketed paste content until \\x1b[201~."""
        while True:
            idx = self._buf.find(b"\x1b[201~")
            if idx >= 0:
                raw = bytes(self._buf[:idx])
                del self._buf[: idx + 6]
            elif not self._fill(0.1):
                raw = bytes(self._buf)
                self._buf.clear()
            else:
                continue
            return Paste(raw.decode("utf-8", errors="replace").replace("\r", "\n"))


def parse_csi(csi: bytes) -> str | None:
    """Parse a CSI (Control Sequence Introducer) payload."""
    if csi[:1] == b"O":
        return None  # focus lost
    # SGR mouse: <button;x;yM or <button;x;ym
    if csi[:1] == b"<":
        return parse_sgr_mouse(csi[1:])
    hit = CSI_KEYS.get(csi) or CSI_KEYS.get(csi[:2])
    if hit:
        return hit
    # Modifier: 1;{mod}{dir}
    if len(csi) >= 4 and csi[:1] == b"1":
        return MOD_KEYS.get((csi[2:3], csi[3:4]))
    return None


_MOUSE_BUTTONS = {64: "scroll-up", 65: "scroll-down"}


def parse_sgr_mouse(payload: bytes) -> str | None:
    """Parse SGR mouse payload: button;x;y{M|m}."""
    try:
        text = payload.decode()
        if text[-1] not in ("M", "m"):
            return None
        button = int(text[:-1].split(";")[0])
    except (ValueError, IndexError, UnicodeDecodeError):
        return None
    return _MOUSE_BUTTONS.get(button)
