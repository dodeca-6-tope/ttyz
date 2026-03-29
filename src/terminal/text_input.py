"""Single-line text input with paste support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from terminal.term import Paste


@dataclass(frozen=True, order=True)
class PasteRange:
    """A half-open [start, end) range marking pasted content in the buffer."""
    start: int
    end: int


class TextInput:
    """Editable text buffer that tracks paste ranges for display."""

    def __init__(self, value: str = "", cursor: int | None = None, pastes: list[PasteRange] | None = None) -> None:
        self.value = value
        self.cursor = cursor if cursor is not None else len(value)
        self.pastes: list[PasteRange] = sorted(pastes) if pastes else []

    # ── Display ──────────────────────────────────────────────────────

    CURSOR_ON = "\033[7m"   # reverse video
    CURSOR_OFF = "\033[27m"

    def display(self) -> str:
        """Render value with paste placeholders and block cursor (reverse video)."""
        text = self._display_text()
        cur = self._display_cursor()
        if cur >= len(text):
            return f"{text}{self.CURSOR_ON} {self.CURSOR_OFF}"
        return f"{text[:cur]}{self.CURSOR_ON}{text[cur]}{self.CURSOR_OFF}{text[cur + 1:]}"

    @staticmethod
    def _sanitize(text: str) -> str:
        """Replace control characters with visible symbols for display."""
        return text.replace("\r", "↵").replace("\n", "↵").replace("\t", " ")

    def _display_text(self) -> str:
        if not self.pastes:
            return self._sanitize(self.value)
        parts: list[str] = []
        pos = 0
        for p in self.pastes:
            parts.append(self._sanitize(self.value[pos:p.start]))
            parts.append(self._paste_label(p.end - p.start))
            pos = p.end
        parts.append(self._sanitize(self.value[pos:]))
        return "".join(parts)

    def _display_cursor(self) -> int:
        if not self.pastes:
            return self.cursor
        offset = 0
        for p in self.pastes:
            if self.cursor <= p.start:
                break
            span = p.end - p.start
            adj = span if self.cursor >= p.end else (self.cursor - p.start)
            offset += len(self._paste_label(span)) - adj
            if self.cursor < p.end:
                break
        return max(0, self.cursor + offset)

    @staticmethod
    def _paste_label(length: int) -> str:
        return f"[Pasted +{length} chars]"

    # ── Mutations ────────────────────────────────────────────────────

    def handle_key(self, key: str | Paste) -> bool:
        """Process a key or paste event. Returns True if handled, False otherwise."""
        if isinstance(key, Paste):
            self._paste(key.text)
            return True
        match key:
            case "left":       self._move_left()
            case "right":      self._move_right()
            case "word-left":  self._word_left()
            case "word-right": self._word_right()
            case "backspace":  self._backspace()
            case "clear-line": self._clear_line()
            case "delete-word": self._delete_word()
            case "home":       self.cursor = 0
            case "end":        self.cursor = len(self.value)
            case "space":      self._insert(" ")
            case c if len(c) == 1 and c.isprintable(): self._insert(c)
            case _:            return False
        return True

    # ── Navigation ───────────────────────────────────────────────────

    def _find_paste(self, pos: int, *, include_end: bool = False) -> PasteRange | None:
        """Return paste range containing pos. With include_end, also matches pos == end."""
        for p in self.pastes:
            if p.start < pos < p.end or (include_end and p.start < pos == p.end):
                return p
        return None

    def _paste_at(self, pos: int) -> PasteRange | None:
        """Return paste range starting at pos, or containing/ending at pos."""
        hit = self._find_paste(pos, include_end=True)
        if hit:
            return hit
        for p in self.pastes:
            if p.start == pos:
                return p
        return None

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
        """Move cursor to start of current/previous word. Pastes are atomic."""
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
        """Move cursor left while pred holds, stopping at paste boundaries."""
        while self.cursor > 0 and pred(self.value[self.cursor + offset]):
            p = self._find_paste(self.cursor + offset)
            if p:
                self.cursor = p.start
                return
            self.cursor -= 1

    def _word_right(self) -> None:
        """Move cursor to start of next word. Pastes are atomic."""
        if self.cursor >= len(self.value):
            return
        paste = self._paste_at(self.cursor)
        if paste:
            self.cursor = paste.end
        self._skip_non_space_right()
        while self.cursor < len(self.value) and self.value[self.cursor] == " ":
            self.cursor += 1

    def _skip_non_space_right(self) -> None:
        """Advance cursor past non-space characters, jumping over pastes."""
        while self.cursor < len(self.value) and self.value[self.cursor] != " ":
            hit = self._paste_at(self.cursor)
            if hit:
                self.cursor = hit.end
                return
            self.cursor += 1

    # ── Insert / Delete ──────────────────────────────────────────────

    def _insert(self, text: str) -> None:
        self._shift_pastes(self.cursor, len(text))
        self.value = self.value[:self.cursor] + text + self.value[self.cursor:]
        self.cursor += len(text)

    def _paste(self, text: str) -> None:
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
            self.value = self.value[:paste.start] + self.value[paste.end:]
            self._shift_pastes(paste.start, -(paste.end - paste.start))
            self.cursor = paste.start
        else:
            self.value = self.value[:self.cursor - 1] + self.value[self.cursor:]
            self.cursor -= 1
            self._shift_pastes(self.cursor, -1)

    def _clear_line(self) -> None:
        removed = self.cursor
        self.value = self.value[self.cursor:]
        shifted = [PasteRange(p.start - removed, p.end - removed) for p in self.pastes if p.end > removed]
        self.pastes = [PasteRange(max(0, p.start), p.end) for p in shifted if p.end > max(0, p.start)]
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
        self.value = self.value[:cut_pos] + self.value[self.cursor:]
        self.cursor = cut_pos
        self._shift_pastes(cut_pos, -removed)
        self.pastes = [p for p in self.pastes if p.end > p.start]

    def _word_boundary_left(self) -> int:
        """Find the start of the word to the left, respecting paste boundaries."""
        before = self.value[:self.cursor].rstrip()
        pos = before.rfind(" ") + 1 if " " in before else 0
        for p in self.pastes:
            if p.start < self.cursor and p.end > pos and p.end <= self.cursor:
                pos = p.end
        return pos

    # ── Paste range helpers ──────────────────────────────────────────

    def _shift_pastes(self, after: int, delta: int) -> None:
        """Shift paste ranges. Splits any range that contains the insertion point."""
        new: list[PasteRange] = []
        for p in self.pastes:
            if p.start >= after:
                new.append(PasteRange(p.start + delta, p.end + delta))
            elif p.end > after:
                if delta > 0:
                    new.append(PasteRange(p.start, after))
                    new.append(PasteRange(after + delta, p.end + delta))
                else:
                    new.append(PasteRange(p.start, p.end + delta))
            else:
                new.append(p)
        self.pastes = [p for p in new if p.end > p.start]
