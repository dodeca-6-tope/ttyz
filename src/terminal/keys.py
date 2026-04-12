"""Key maps, event types, and escape sequence classification."""

from __future__ import annotations

import codecs
import os
import select
from dataclasses import dataclass

# ── Event types ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Key:
    """A keypress event."""

    name: str  # "a", "enter", "tab", "ctrl-d", "esc", etc.
    shift: bool = False
    alt: bool = False
    ctrl: bool = False
    super: bool = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.name == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass(frozen=True)
class Paste:
    """Bracketed paste content."""

    text: str


@dataclass(frozen=True)
class Mouse:
    """Mouse event."""

    action: str  # "scroll-up", "scroll-down"
    x: int = 0
    y: int = 0


@dataclass(frozen=True)
class Resize:
    """Terminal resize."""

    cols: int
    lines: int


@dataclass(frozen=True)
class Focus:
    """Terminal focus change."""

    gained: bool


Event = Key | Paste | Mouse | Resize | Focus


# ── Key maps ─────────────────────────────────────────────────────────

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


# ── Kitty keyboard protocol ─────────────────────────────────────────

# Enable/disable sequences for Kitty keyboard protocol
# Flags: 0b1 = disambiguate, 0b10 = report event types,
#         0b100 = report alternate keys, 0b1000 = report all keys
KITTY_ENABLE = "\033[>1u"  # push mode 1 (disambiguate escape codes)
KITTY_DISABLE = "\033[<u"  # pop keyboard mode
KITTY_QUERY = "\033[?u"  # query current keyboard mode

# Kitty protocol: unicode codepoint → key name
_KITTY_SPECIAL: dict[int, str] = {
    9: "tab",
    13: "enter",
    27: "esc",
    127: "backspace",
    57358: "caps-lock",
    57359: "scroll-lock",
    57360: "num-lock",
    57361: "print-screen",
    57362: "pause",
    57363: "menu",
    57376: "f13",
    57377: "f14",
    57378: "f15",
    57379: "f16",
    57380: "f17",
    57381: "f18",
    57382: "f19",
    57383: "f20",
    57384: "f21",
    57385: "f22",
    57386: "f23",
    57387: "f24",
    57388: "f25",
    57399: "kp-0",
    57400: "kp-1",
    57401: "kp-2",
    57402: "kp-3",
    57403: "kp-4",
    57404: "kp-5",
    57405: "kp-6",
    57406: "kp-7",
    57407: "kp-8",
    57408: "kp-9",
    57409: "kp-decimal",
    57410: "kp-divide",
    57411: "kp-multiply",
    57412: "kp-subtract",
    57413: "kp-add",
    57414: "kp-enter",
    57415: "kp-equal",
    57416: "kp-separator",
    57417: "kp-left",
    57418: "kp-right",
    57419: "kp-up",
    57420: "kp-down",
    57421: "kp-page-up",
    57422: "kp-page-down",
    57423: "kp-home",
    57424: "kp-end",
    57425: "kp-insert",
    57426: "kp-delete",
    57427: "kp-begin",
    57428: "media-play",
    57429: "media-pause",
    57430: "media-play-pause",
    57431: "media-reverse",
    57432: "media-stop",
    57433: "media-fast-forward",
    57434: "media-rewind",
    57435: "media-next",
    57436: "media-prev",
    57437: "media-record",
    57438: "volume-down",
    57439: "volume-up",
    57440: "volume-mute",
}

# CSI number ~ keys (legacy function keys with Kitty modifiers)
_KITTY_TILDE: dict[int, str] = {
    2: "insert",
    3: "delete",
    5: "page-up",
    6: "page-down",
    7: "home",
    8: "end",
    11: "f1",
    12: "f2",
    13: "f3",
    14: "f4",
    15: "f5",
    17: "f6",
    18: "f7",
    19: "f8",
    20: "f9",
    21: "f10",
    23: "f11",
    24: "f12",
}

# CSI 1;mods X letter-terminated keys
_KITTY_LETTER: dict[int, str] = {
    ord("A"): "up",
    ord("B"): "down",
    ord("C"): "right",
    ord("D"): "left",
    ord("H"): "home",
    ord("F"): "end",
    ord("P"): "f1",
    ord("Q"): "f2",
    ord("R"): "f3",  # Note: conflicts with CPR response
    ord("S"): "f4",
}


def _decode_kitty_mods(mods_val: int) -> tuple[bool, bool, bool, bool]:
    """Decode Kitty modifier value (1-based) into (shift, alt, ctrl, super)."""
    m = mods_val - 1
    return (bool(m & 1), bool(m & 2), bool(m & 4), bool(m & 8))


def _kitty_key(name: str, shift: bool, alt: bool, ctrl: bool, sup: bool) -> Key:
    """Build a Key from Kitty protocol data."""
    return Key(name=name, shift=shift, alt=alt, ctrl=ctrl, super=sup)


def parse_kitty_csi_u(params: str) -> Key | None:
    """Parse a Kitty keyboard protocol CSI u sequence.

    Format: CSI unicode-key-code:shifted-key ; modifiers:event-type u
    """
    parts = params.split(";")
    # Parse key code (may have :shifted-key suffix)
    key_part = parts[0].split(":")
    try:
        keycode = int(key_part[0])
    except (ValueError, IndexError):
        return None

    # Parse modifiers
    shift = alt = ctrl = sup = False
    if len(parts) >= 2:
        mod_part = parts[1].split(":")
        try:
            mods_val = int(mod_part[0]) if mod_part[0] else 1
        except ValueError:
            mods_val = 1
        shift, alt, ctrl, sup = _decode_kitty_mods(mods_val)

    # Resolve key name
    name = _KITTY_SPECIAL.get(keycode)
    if name is None:
        if 1 <= keycode <= 26 and ctrl:
            # Ctrl+letter
            name = chr(keycode + 96)  # 1->a, 2->b, etc.
        elif 32 <= keycode <= 126 or keycode >= 0x80:
            name = chr(keycode)
        else:
            return None

    return _kitty_key(name, shift, alt, ctrl, sup)


# ── Reader ───────────────────────────────────────────────────────────


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

    def read(self, timeout: float = 1 / 60) -> Event | None:
        """Read a single input event. Returns None on timeout."""
        if not self._fill(timeout):
            return None
        return self._classify()

    def _classify(self) -> Event | None:
        ch = self._consume()
        if ch == b"\x1b":
            return self._read_escape()
        if ch == b"\x03":
            raise KeyboardInterrupt
        name = BYTE_KEYS.get(ch)
        if name:
            return Key(name)
        text = self._read_utf8(ch)
        return Key(text) if text else None

    def _read_utf8(self, initial: bytes) -> str | None:
        result = self._utf8.decode(initial)
        while not result:
            if not self._fill(0.01):
                self._utf8.reset()
                return None
            result = self._utf8.decode(self._consume())
        return result

    def _read_escape(self) -> Event | None:
        """Parse an escape sequence from the buffer."""
        if not self._fill(0.004):
            return Key("esc")
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
            name = DBL_ESC_KEYS.get(self._consume())
            return Key(name) if name else None
        # Alt/Option + key
        name = ESC_KEYS.get(self._consume())
        return Key(name) if name else None

    def _csi_end(self) -> int | None:
        """Find the index of the CSI terminator byte (0x40–0x7E), or None."""
        for i in range(len(self._buf)):
            if 0x40 <= self._buf[i] <= 0x7E:
                return i
        return None

    def _read_csi(self) -> Event | None:
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


# ── CSI parsing ──────────────────────────────────────────────────────


def parse_csi(csi: bytes) -> Event | None:
    """Parse a CSI payload.

    Priority: mouse → Kitty CSI u → simple keys → parameterized keys.
    Legacy modifier maps (MOD_KEYS) take priority over Kitty letter/tilde
    parsers so Option+Arrow still produces "word-right" from legacy terminals.
    """
    if csi[:1] == b"O":
        return Focus(gained=False)
    if csi[:1] == b"I":
        return Focus(gained=True)
    if csi[:1] == b"<":
        return parse_sgr_mouse(csi[1:])
    if csi[-1:] == b"u":
        return parse_kitty_csi_u(csi[:-1].decode("ascii", errors="replace"))

    # Simple keys (no parameters): A→up, H→home, 3~→delete, etc.
    hit = CSI_KEYS.get(csi) or CSI_KEYS.get(csi[:2])
    if hit:
        return Key(hit)

    # Parameterized keys (contain ";")
    if b";" not in csi:
        return None

    # Legacy modifier arrows first (Option/Cmd/Shift + arrow → semantic names)
    if len(csi) >= 4 and csi[:1] == b"1":
        legacy = MOD_KEYS.get((csi[2:3], csi[3:4]))
        if legacy:
            return Key(legacy)

    # Kitty modified keys
    final = csi[-1]
    if final == ord("~"):
        return _parse_kitty_tilde(csi)
    if 0x40 <= final <= 0x7E:
        return _parse_kitty_letter(csi)
    return None


def _parse_kitty_tilde(csi: bytes) -> Key | None:
    """Parse CSI number ; modifiers ~ (Kitty modified function/special keys)."""
    params = csi[:-1].decode("ascii", errors="replace")
    parts = params.split(";")
    if len(parts) < 2:
        return None
    try:
        keynum = int(parts[0])
        mods_val = int(parts[1].split(":")[0]) if parts[1] else 1
    except ValueError:
        return None
    name = _KITTY_TILDE.get(keynum)
    if name is None:
        return None
    shift, alt, ctrl, sup = _decode_kitty_mods(mods_val)
    return _kitty_key(name, shift, alt, ctrl, sup)


def _parse_kitty_letter(csi: bytes) -> Key | None:
    """Parse CSI 1 ; modifiers [A-Z] (Kitty modified arrow/function keys)."""
    params = csi[:-1].decode("ascii", errors="replace")
    final = csi[-1]
    parts = params.split(";")
    if len(parts) < 2:
        return None
    try:
        mods_val = int(parts[1].split(":")[0]) if parts[1] else 1
    except ValueError:
        return None
    name = _KITTY_LETTER.get(final)
    if name is None:
        return None
    shift, alt, ctrl, sup = _decode_kitty_mods(mods_val)
    return _kitty_key(name, shift, alt, ctrl, sup)


def parse_sgr_mouse(payload: bytes) -> Mouse | None:
    """Parse SGR mouse payload: button;x;y{M|m}."""
    try:
        text = payload.decode()
        if text[-1] not in ("M", "m"):
            return None
        parts = text[:-1].split(";")
        button = int(parts[0])
        x = int(parts[1]) if len(parts) > 1 else 0
        y = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError, UnicodeDecodeError):
        return None
    action = {64: "scroll-up", 65: "scroll-down"}.get(button)
    if action is None:
        return None
    return Mouse(action=action, x=x, y=y)
