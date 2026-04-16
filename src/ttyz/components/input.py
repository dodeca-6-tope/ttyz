"""Text input component with paste support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ttyz.components.base import Node
from ttyz.keys import Event, Key, Paste


@dataclass(frozen=True, order=True)
class PasteRange:
    """A half-open [start, end) range marking pasted content in the buffer."""

    start: int
    end: int


class InputBuffer:
    """Editable text buffer that tracks paste ranges."""

    def __init__(
        self,
        value: str = "",
        cursor: int | None = None,
        pastes: list[PasteRange] | None = None,
    ) -> None:
        self.value = value
        self.cursor = cursor if cursor is not None else len(value)
        self.pastes: list[PasteRange] = sorted(pastes) if pastes else []

    def handle_key(self, event: Event) -> bool:
        """Process an input event. Returns True if handled, False otherwise."""
        if isinstance(event, Paste):
            self._paste(event.text)
            return True
        if not isinstance(event, Key):
            return False
        match event.name:
            case "left":
                self._move_left()
            case "right":
                self._move_right()
            case "word-left":
                self._word_left()
            case "word-right":
                self._word_right()
            case "backspace":
                self._backspace()
            case "clear-line":
                self._clear_line()
            case "delete-word":
                self._delete_word()
            case "home":
                self.cursor = 0
            case "end":
                self.cursor = len(self.value)
            case "space":
                self._insert(" ")
            case c if len(c) == 1 and c.isprintable():
                self._insert(c)
            case _:
                return False
        return True

    def _find_paste(self, pos: int, *, include_end: bool = False) -> PasteRange | None:
        return next(
            (
                p
                for p in self.pastes
                if p.start < pos < p.end or (include_end and p.start < pos == p.end)
            ),
            None,
        )

    def _move_left(self) -> None:
        if self.cursor == 0:
            return
        new = self.cursor - 1
        paste = self._find_paste(new)
        self.cursor = paste.start if paste else new

    def _move_right(self) -> None:
        if self.cursor >= len(self.value):
            return
        new = self.cursor + 1
        paste = self._find_paste(new)
        self.cursor = paste.end if paste else new

    def _word_left(self) -> None:
        if self.cursor == 0:
            return
        paste = self._find_paste(self.cursor, include_end=True)
        if paste:
            self.cursor = paste.start
            return
        self.cursor -= 1
        self._skip_left(lambda c: c == " ")
        self._skip_left(lambda c: c != " ", offset=-1)

    def _skip_left(self, pred: Callable[[str], bool], offset: int = 0) -> None:
        while self.cursor > 0 and pred(self.value[self.cursor + offset]):
            p = self._find_paste(self.cursor + offset)
            if p:
                if self._find_paste(self.cursor) == p:
                    self.cursor = p.start
                return
            self.cursor -= 1

    def _paste_starting_at(self, pos: int) -> PasteRange | None:
        return next((p for p in self.pastes if p.start == pos), None)

    def _word_right(self) -> None:
        if self.cursor >= len(self.value):
            return
        paste = self._find_paste(self.cursor) or self._paste_starting_at(self.cursor)
        if paste:
            self.cursor = paste.end
            return
        while self.cursor < len(self.value) and self.value[self.cursor] == " ":
            self.cursor += 1
        paste = self._paste_starting_at(self.cursor)
        if paste:
            self.cursor = paste.end
            return
        while self.cursor < len(self.value) and self.value[self.cursor] != " ":
            if self._paste_starting_at(self.cursor):
                return
            self.cursor += 1

    def _insert(self, text: str) -> None:
        self._shift_pastes(self.cursor, len(text))
        self.value = self.value[: self.cursor] + text + self.value[self.cursor :]
        self.cursor += len(text)

    def _paste(self, text: str) -> None:
        if not text:
            return
        start = self.cursor
        self._insert(text)
        self.pastes.append(PasteRange(start, start + len(text)))
        self.pastes.sort()

    def _backspace(self) -> None:
        if self.cursor == 0:
            return
        paste = self._find_paste(self.cursor, include_end=True)
        if paste:
            self.pastes.remove(paste)
            self.value = self.value[: paste.start] + self.value[paste.end :]
            self._shift_pastes(paste.start, -(paste.end - paste.start))
            self.cursor = paste.start
        else:
            self.value = self.value[: self.cursor - 1] + self.value[self.cursor :]
            self.cursor -= 1
            self._shift_pastes(self.cursor, -1)

    def _clear_line(self) -> None:
        cut = self.cursor
        self.value = self.value[cut:]
        self.pastes = [
            PasteRange(max(0, p.start - cut), p.end - cut)
            for p in self.pastes
            if p.end > cut
        ]
        self.cursor = 0

    def _delete_word(self) -> None:
        if self.cursor == 0:
            return
        if self._find_paste(self.cursor, include_end=True):
            self._backspace()
            return
        cut_pos = self._word_boundary_left()
        removed = self.cursor - cut_pos
        if removed == 0:
            return
        self.value = self.value[:cut_pos] + self.value[self.cursor :]
        self.cursor = cut_pos
        self._shift_pastes(cut_pos, -removed)
        self.pastes = [p for p in self.pastes if p.end > p.start]

    def _word_boundary_left(self) -> int:
        before = self.value[: self.cursor].rstrip()
        pos = before.rfind(" ") + 1 if " " in before else 0
        for p in self.pastes:
            if p.start < self.cursor and p.end > pos and p.end <= self.cursor:
                pos = p.end
        return pos

    def _shift_pastes(self, after: int, delta: int) -> None:
        new: list[PasteRange] = []
        for p in self.pastes:
            if p.start >= after:
                new.append(PasteRange(p.start + delta, p.end + delta))
            elif p.end <= after:
                new.append(p)
            elif delta > 0:
                new.append(PasteRange(p.start, after))
                new.append(PasteRange(after + delta, p.end + delta))
            else:
                new.append(PasteRange(p.start, p.end + delta))
        self.pastes = [p for p in new if p.end > p.start]


_PASTE_LABEL = "[Pasted +{} chars]"


def _sanitize(text: str) -> str:
    return text.replace("\r", "↵").replace("\n", "↵").replace("\t", " ")


def display_text(ti: InputBuffer) -> str:
    """Render buffer value with paste placeholders."""
    if not ti.pastes:
        return _sanitize(ti.value)
    parts: list[str] = []
    pos = 0
    for p in ti.pastes:
        parts.append(_sanitize(ti.value[pos : p.start]))
        parts.append(_PASTE_LABEL.format(p.end - p.start))
        pos = p.end
    parts.append(_sanitize(ti.value[pos:]))
    return "".join(parts)


def display_cursor(ti: InputBuffer) -> int:
    """Compute cursor position in display text (accounting for paste labels)."""
    if not ti.pastes:
        return ti.cursor
    offset = 0
    for p in ti.pastes:
        if ti.cursor <= p.start:
            break
        span = p.end - p.start
        adj = span if ti.cursor >= p.end else (ti.cursor - p.start)
        offset += len(_PASTE_LABEL.format(span)) - adj
        if ti.cursor < p.end:
            break
    return max(0, ti.cursor + offset)


class Input(Node):
    """Text input node."""

    __slots__ = ("buffer", "placeholder", "active")


def input(
    ti: InputBuffer,
    *,
    placeholder: str = "",
    active: bool = True,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Input:
    node = Input((), grow or 0, width, height, bg, overflow)
    node.buffer = ti
    node.placeholder = placeholder
    node.active = active

    return node
