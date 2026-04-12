"""Terminal control commands — typed objects for tty.write().

Each command is a frozen dataclass with a sequence() method that returns
the escape string. Pass them to tty.write():

    tty.write(SetTitle("my app"), CursorShape(2), ShowCursor())
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

# ── Cursor ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CursorShape:
    """Set cursor shape. 0=default, 1=block blink, 2=block,
    3=underline blink, 4=underline, 5=bar blink, 6=bar."""

    shape: int

    def sequence(self) -> str:
        return f"\033[{self.shape} q"


@dataclass(frozen=True)
class ShowCursor:
    def sequence(self) -> str:
        return "\033[?25h"


@dataclass(frozen=True)
class HideCursor:
    def sequence(self) -> str:
        return "\033[?25l"


@dataclass(frozen=True)
class MoveTo:
    """Move cursor to row, col (1-based)."""

    row: int
    col: int

    def sequence(self) -> str:
        return f"\033[{self.row};{self.col}H"


@dataclass(frozen=True)
class CursorUp:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}A"


@dataclass(frozen=True)
class CursorDown:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}B"


@dataclass(frozen=True)
class CursorForward:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}C"


@dataclass(frozen=True)
class CursorBack:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}D"


@dataclass(frozen=True)
class SaveCursor:
    def sequence(self) -> str:
        return "\033[s"


@dataclass(frozen=True)
class RestoreCursor:
    def sequence(self) -> str:
        return "\033[u"


# ── Erase ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EraseDisplay:
    """0=below, 1=above, 2=all, 3=all+scrollback."""

    mode: int = 0

    def sequence(self) -> str:
        return f"\033[{self.mode}J"


@dataclass(frozen=True)
class EraseLine:
    """0=to right, 1=to left, 2=entire line."""

    mode: int = 0

    def sequence(self) -> str:
        return f"\033[{self.mode}K"


@dataclass(frozen=True)
class EraseChars:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}X"


# ── Scroll ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SetScrollRegion:
    """Set scrolling region (1-based inclusive)."""

    top: int
    bottom: int

    def sequence(self) -> str:
        return f"\033[{self.top};{self.bottom}r"


@dataclass(frozen=True)
class ResetScrollRegion:
    def sequence(self) -> str:
        return "\033[r"


@dataclass(frozen=True)
class ScrollUp:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}S"


@dataclass(frozen=True)
class ScrollDown:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}T"


# ── Insert / Delete ──────────────────────────────────────────────────


@dataclass(frozen=True)
class InsertLines:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}L"


@dataclass(frozen=True)
class DeleteLines:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}M"


@dataclass(frozen=True)
class InsertChars:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}@"


@dataclass(frozen=True)
class DeleteChars:
    n: int = 1

    def sequence(self) -> str:
        return f"\033[{self.n}P"


# ── OSC ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SetTitle:
    title: str

    def sequence(self) -> str:
        return f"\033]2;{self.title}\033\\"


@dataclass(frozen=True)
class SetClipboard:
    content: str

    def sequence(self) -> str:
        encoded = base64.b64encode(self.content.encode()).decode()
        return f"\033]52;c;{encoded}\033\\"


# ── Protocol ─────────────────────────────────────────────────────────

Command = (
    CursorShape
    | ShowCursor
    | HideCursor
    | MoveTo
    | CursorUp
    | CursorDown
    | CursorForward
    | CursorBack
    | SaveCursor
    | RestoreCursor
    | EraseDisplay
    | EraseLine
    | EraseChars
    | SetScrollRegion
    | ResetScrollRegion
    | ScrollUp
    | ScrollDown
    | InsertLines
    | DeleteLines
    | InsertChars
    | DeleteChars
    | SetTitle
    | SetClipboard
)
