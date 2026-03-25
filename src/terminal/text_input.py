"""Single-line text input with paste support."""

from __future__ import annotations

from terminal.term import Paste


class TextInput:
    """Editable text buffer that tracks paste ranges for display."""

    def __init__(self, value: str = "", cursor: int | None = None, pastes: list[tuple[int, int]] | None = None) -> None:
        self.value = value
        self.cursor = cursor if cursor is not None else len(value)
        self.pastes: list[tuple[int, int]] = sorted(pastes) if pastes else []

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
        for start, end in self.pastes:
            parts.append(self._sanitize(self.value[pos:start]))
            parts.append(self._paste_label(end - start))
            pos = end
        parts.append(self._sanitize(self.value[pos:]))
        return "".join(parts)

    def _display_cursor(self) -> int:
        if not self.pastes:
            return self.cursor
        offset = 0
        for start, end in self.pastes:
            label_len = len(self._paste_label(end - start))
            real_len = end - start
            if self.cursor <= start:
                break
            if self.cursor >= end:
                offset += label_len - real_len
            else:
                # Cursor inside a paste — snap to end of label
                offset += label_len - (self.cursor - start)
                break
        return max(0, self.cursor + offset)

    @staticmethod
    def _paste_label(length: int) -> str:
        return f"[Pasted +{length} chars]"

    # ── Mutations ────────────────────────────────────────────────────

    _KEY_ACTIONS: dict[str, str] = {
        "left": "_move_left",
        "right": "_move_right",
        "word-left": "_word_left",
        "word-right": "_word_right",
        "backspace": "_backspace",
        "clear-line": "_clear_line",
        "delete-word": "_delete_word",
    }

    def handle_key(self, key: str | Paste) -> bool:
        """Process a key or paste event. Returns True if handled, False otherwise."""
        if isinstance(key, Paste):
            self._paste(key.text)
            return True
        action = self._KEY_ACTIONS.get(key)
        if action:
            getattr(self, action)()
            return True
        if key == "home":
            self.cursor = 0
        elif key == "end":
            self.cursor = len(self.value)
        elif key == "space":
            self._insert(" ")
        elif len(key) == 1 and key.isprintable():
            self._insert(key)
        else:
            return False
        return True

    # ── Navigation ───────────────────────────────────────────────────

    def _find_paste(self, pos: int, *, include_end: bool = False) -> tuple[int, int] | None:
        """Return paste range containing pos. With include_end, also matches pos == end."""
        for s, e in self.pastes:
            if s < pos < e or (include_end and s < pos == e):
                return (s, e)
        return None

    def _move_left(self) -> None:
        if self.cursor == 0:
            return
        new = self.cursor - 1
        paste = self._find_paste(new)
        self.cursor = paste[0] if paste else new

    def _move_right(self) -> None:
        if self.cursor >= len(self.value):
            return
        new = self.cursor + 1
        paste = self._find_paste(new)
        self.cursor = paste[1] if paste else new

    def _word_left(self) -> None:
        """Move cursor to start of current/previous word. Pastes are atomic."""
        if self.cursor == 0:
            return
        paste = self._find_paste(self.cursor, include_end=True)
        if paste:
            self.cursor = paste[0]
            return
        self.cursor -= 1
        while self.cursor > 0 and self.value[self.cursor] == " ":
            p = self._find_paste(self.cursor)
            if p:
                self.cursor = p[0]
                return
            self.cursor -= 1
        while self.cursor > 0 and self.value[self.cursor - 1] != " ":
            p = self._find_paste(self.cursor - 1)
            if p:
                self.cursor = p[0]
                return
            self.cursor -= 1

    def _word_right(self) -> None:
        """Move cursor to start of next word. Pastes are atomic."""
        if self.cursor >= len(self.value):
            return
        paste = self._find_paste(self.cursor, include_end=True)
        if not paste:
            for s, e in self.pastes:
                if s == self.cursor:
                    paste = (s, e)
                    break
        if paste:
            self.cursor = paste[1]
        while self.cursor < len(self.value) and self.value[self.cursor] != " ":
            for s, e in self.pastes:
                if s == self.cursor:
                    self.cursor = e
                    break
            else:
                self.cursor += 1
                continue
            break
        while self.cursor < len(self.value) and self.value[self.cursor] == " ":
            self.cursor += 1

    # ── Insert / Delete ──────────────────────────────────────────────

    def _insert(self, text: str) -> None:
        self._shift_pastes(self.cursor, len(text))
        self.value = self.value[:self.cursor] + text + self.value[self.cursor:]
        self.cursor += len(text)

    def _paste(self, text: str) -> None:
        start = self.cursor
        self._insert(text)
        self.pastes.append((start, start + len(text)))
        self.pastes.sort()

    def _backspace(self) -> None:
        if self.cursor == 0:
            return
        # If cursor is inside or at the end of a paste, delete the whole paste
        paste = self._find_paste(self.cursor, include_end=True)
        if paste:
            start, end = paste
            self.pastes.remove(paste)
            self.value = self.value[:start] + self.value[end:]
            self._shift_pastes(start, -(end - start))
            self.cursor = start
        else:
            self.value = self.value[:self.cursor - 1] + self.value[self.cursor:]
            self.cursor -= 1
            self._shift_pastes(self.cursor, -1)

    def _clear_line(self) -> None:
        removed = self.cursor
        self.value = self.value[self.cursor:]
        self.pastes = [(s - removed, e - removed) for s, e in self.pastes if e > removed]
        self.pastes = [(max(0, s), e) for s, e in self.pastes if e > s]
        self.cursor = 0

    def _delete_word(self) -> None:
        if self.cursor == 0:
            return
        paste = self._find_paste(self.cursor, include_end=True)
        if paste:
            self._backspace()
            return
        # Find word boundary but don't cross into a paste
        before = self.value[:self.cursor].rstrip()
        cut_pos = before.rfind(" ") + 1 if " " in before else 0
        # Clamp to the end of any paste that sits between cut_pos and cursor
        for s, e in self.pastes:
            if s < self.cursor and e > cut_pos and e <= self.cursor:
                cut_pos = e
        removed = self.cursor - cut_pos
        if removed == 0:
            return
        self.value = self.value[:cut_pos] + self.value[self.cursor:]
        self.cursor = cut_pos
        self._shift_pastes(cut_pos, -removed)
        self.pastes = [(s, e) for s, e in self.pastes if e > s]

    # ── Paste range helpers ──────────────────────────────────────────

    def _shift_pastes(self, after: int, delta: int) -> None:
        """Shift paste ranges. Splits any range that contains the insertion point."""
        new: list[tuple[int, int]] = []
        for s, e in self.pastes:
            if s >= after:
                new.append((s + delta, e + delta))
            elif e > after:
                # Insertion inside this paste — split around the insertion
                if delta > 0:
                    new.append((s, after))
                    new.append((after + delta, e + delta))
                else:
                    # Deletion inside paste — shrink it
                    new.append((s, e + delta))
            else:
                new.append((s, e))
        self.pastes = [(s, e) for s, e in new if e > s]
