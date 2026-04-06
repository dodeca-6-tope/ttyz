"""ANSI-aware text — a string that doubles as a display component."""

from __future__ import annotations

from terminal.components.base import Component
from terminal.measure import display_width, slice_at_width, strip_ansi


def truncate(s: str, max_width: int, ellipsis: bool = False) -> str:
    """Truncate a string to max_width visible characters."""
    stripped = strip_ansi(s)
    if display_width(stripped) <= max_width:
        return s
    if ellipsis:
        return slice_at_width(stripped, max_width - 1) + "…"
    return slice_at_width(stripped, max_width)


def _wrap_line(line: str, width: int) -> list[str]:
    """Word-wrap a line, falling back to character-wrap for long words."""
    if display_width(line) <= width:
        return [line]
    lines: list[str] = []
    current = ""
    for word in line.split(" "):
        joined = f"{current} {word}" if current else word
        if display_width(joined) <= width:
            current = joined
            continue
        if current:
            lines.append(current)
        current = ""
        while display_width(word) > width:
            chunk = slice_at_width(word, width)
            lines.append(chunk)
            word = word[len(chunk) :]
        current = word
    if current:
        lines.append(current)
    return lines or [""]


class Text(Component):
    """ANSI-aware string that doubles as a display component."""

    def __init__(
        self,
        value: object = "",
        *,
        max_width: int | str | None = None,
        wrap: bool = False,
        padding: int = 0,
        padding_left: int | None = None,
        padding_right: int | None = None,
        ellipsis: bool = False,
    ) -> None:
        raw = str(value)
        self._fill = max_width == "fill"
        self._ellipsis = ellipsis
        if isinstance(max_width, int):
            raw = truncate(raw, max_width, ellipsis=ellipsis)
        self._raw = raw
        self._wrap = wrap
        self._lines = raw.splitlines() or [""]
        self._visible = max((display_width(l) for l in self._lines), default=0)
        self._pad_left = padding if padding_left is None else padding_left
        self._pad_right = padding if padding_right is None else padding_right

    def __len__(self) -> int:
        return self._visible

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return f"Text({self._raw!r})"

    def __add__(self, other: object) -> Text:
        return Text(self._raw + str(other))

    def __radd__(self, other: object) -> Text:
        return Text(str(other) + self._raw)

    def __format__(self, format_spec: str) -> str:
        return self._raw.__format__(format_spec)

    def pad(self, width: int, align: str = "left") -> Text:
        gap = width - self._visible
        if gap <= 0:
            return self
        spaces = " " * gap
        if align == "left":
            return Text(self._raw + spaces)
        return Text(spaces + self._raw)

    def flex_basis(self) -> int:
        if self._fill:
            return 0
        return self._visible + self._pad_left + self._pad_right

    def flex_grow_width(self) -> int:
        return 1 if self._fill else 0

    def render(self, width: int, height: int | None = None) -> list[str]:
        inner = width - self._pad_left - self._pad_right
        pad = " " * self._pad_left
        pad_r = " " * self._pad_right
        should_truncate = self._fill and self._visible > inner

        chunks: list[str] = []
        for line in self._lines:
            raw = (
                truncate(line, inner, ellipsis=self._ellipsis)
                if should_truncate
                else line
            )
            if self._wrap and inner > 0:
                chunks.extend(_wrap_line(raw, inner))
            else:
                chunks.append(raw)
        return [f"{pad}{c}{pad_r}" for c in chunks]


text = Text
