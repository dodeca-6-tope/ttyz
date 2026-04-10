"""ANSI-aware text — a string that doubles as a display component."""

from __future__ import annotations

from terminal.components.base import Renderable, frame
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


def _truncate_line(line: str, width: int, mode: str) -> str:
    """Truncate a line with ellipsis according to the given mode."""
    stripped = strip_ansi(line)
    if display_width(stripped) <= width:
        return line
    if width <= 0:
        return ""
    if mode == "head":
        return "…" + slice_at_width(stripped[::-1], width - 1)[::-1]
    if mode == "middle":
        left_w = (width - 1) // 2
        right_w = width - 1 - left_w
        return (
            slice_at_width(stripped, left_w)
            + "…"
            + slice_at_width(stripped[::-1], right_w)[::-1]
        )
    # tail (default)
    return slice_at_width(stripped, width - 1) + "…"


class Text:
    """ANSI-aware string helper — measures visible width, supports padding."""

    __slots__ = ("_raw", "_visible")

    def __init__(self, value: object = "") -> None:
        raw = str(value)
        self._raw = raw
        self._visible = display_width(raw)  # C display_width already skips ANSI

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


def _parse_lines(value: object) -> tuple[list[str], int]:
    """Parse value into lines and compute the max display width."""
    raw = value if isinstance(value, str) else str(value)
    if "\n" not in raw:
        return [raw], display_width(raw)
    lines = raw.splitlines() or [""]
    return lines, max(display_width(l) for l in lines)


def text(
    value: object = "",
    *,
    wrap: bool = False,
    truncation: str | None = None,
    padding: int = 0,
    padding_left: int | None = None,
    padding_right: int | None = None,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Renderable:
    lines, visible_w = _parse_lines(value)
    pl = padding if padding_left is None else padding_left
    pr = padding if padding_right is None else padding_right
    basis = visible_w + pl + pr

    # Branch at build time so the per-frame render avoids feature checks.
    if not wrap and not truncation and not pl and not pr:

        def render(w: int, h: int | None = None) -> list[str]:
            return lines

    elif not wrap and not truncation:
        pad_l = " " * pl
        pad_r = " " * pr

        def render(w: int, h: int | None = None) -> list[str]:
            return [f"{pad_l}{c}{pad_r}" for c in lines]

    else:
        mode = truncation
        pad_l = " " * pl
        pad_r = " " * pr

        def render(w: int, h: int | None = None) -> list[str]:
            inner = w - pl - pr
            chunks: list[str] = []
            for line in lines:
                if wrap and inner > 0:
                    chunks.extend(_wrap_line(line, inner))
                elif mode and inner > 0:
                    chunks.append(_truncate_line(line, inner, mode))
                else:
                    chunks.append(line)
            if not pl and not pr:
                return chunks
            return [f"{pad_l}{c}{pad_r}" for c in chunks]

    # Skip frame() indirection when no constraints — avoids an extra Renderable.
    if width is None and height is None and bg is None and overflow == "visible":
        return Renderable(render, basis, grow or 0)
    return frame(Renderable(render, basis), width, height, grow, bg, overflow)
