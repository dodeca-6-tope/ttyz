"""ZStack — layers children on top of each other."""

from __future__ import annotations

from terminal.components.base import Component
from terminal.measure import ANSI_RE, char_width, display_width


class ZStack(Component):
    _ALIGNS = {
        "top-left",
        "top",
        "top-right",
        "left",
        "center",
        "right",
        "bottom-left",
        "bottom",
        "bottom-right",
    }

    def __init__(
        self,
        children: list[Component],
        *,
        align: str = "top-left",
    ) -> None:
        if align not in self._ALIGNS:
            raise ValueError(f"unknown align {align!r}")
        self._children = children
        self._align = align

    def flex_basis(self) -> int:
        return max((c.flex_basis() for c in self._children), default=0)

    def flex_grow_width(self) -> int:
        return max((c.flex_grow_width() for c in self._children), default=0)

    def flex_grow_height(self) -> int:
        return max((c.flex_grow_height() for c in self._children), default=0)

    def render(self, width: int, height: int | None = None) -> list[str]:
        if not self._children:
            return [""]
        # Render children, passing height only to growers (consistent with HStack)
        layers = [
            c.render(width, height) if c.flex_grow_height() else c.render(width)
            for c in self._children
        ]
        # Base height is the tallest layer, or the given height
        height = height or max(len(layer) for layer in layers)
        # Start with empty canvas
        canvas = [" " * width for _ in range(height)]
        # Paint each layer on top
        for layer in layers:
            layer_w = max((display_width(l) for l in layer), default=0)
            row_off, col_off = _offsets(
                self._align, (width, height), (layer_w, len(layer))
            )
            start = max(0, -row_off)
            end = min(len(layer), height - row_off)
            for i in range(start, end):
                canvas[row_off + i] = _stamp(
                    canvas[row_off + i], col_off, layer[i], width
                )
        return canvas


_V_OFFSETS = {"top": 0, "center": 0.5, "bottom": 1}
_H_OFFSETS = {"left": 0, "center": 0.5, "right": 1}


def _offsets(
    align: str, canvas: tuple[int, int], layer: tuple[int, int]
) -> tuple[int, int]:
    """Compute (row_offset, col_offset) for alignment."""
    parts = align.split("-") if "-" in align else [align, align]
    vf = next((_V_OFFSETS[p] for p in parts if p in _V_OFFSETS), 0)
    hf = next((_H_OFFSETS[p] for p in parts if p in _H_OFFSETS), 0)
    w, h = canvas
    lw, lh = layer
    return max(0, int((h - lh) * vf)), max(0, int((w - lw) * hf))


def _active_ansi(s: str) -> str:
    """Return the ANSI state string active at the end of s."""
    if "\033" not in s:
        return ""
    codes: list[str] = []
    for m in ANSI_RE.finditer(s):
        params = m.group()[2:-1]
        if params in ("0", ""):
            codes.clear()
        else:
            codes.append(params)
    return f"\033[{';'.join(codes)}m" if codes else ""


def _split_at_col(s: str, col: int) -> tuple[str, str]:
    """Split a string at a visible column, preserving ANSI codes."""
    visible = 0
    pos = 0
    n = len(s)
    while pos < n and visible < col:
        if s[pos] == "\033" and pos + 1 < n and s[pos + 1] == "[":
            end = pos + 2
            while end < n and s[end] != "m":
                end += 1
            pos = end + 1
        else:
            visible += char_width(s[pos])
            pos += 1
    return s[:pos], s[pos:]


def _stamp(base: str, col: int, line: str, width: int) -> str:
    """Write line onto base at col, overwriting existing content."""
    line_w = display_width(line)
    if col == 0 and line_w >= width:
        return line
    # Pad base to width if needed
    base_w = display_width(base)
    if base_w < width:
        base = base + " " * (width - base_w)
    # Split base at visible column boundaries
    left, rest = _split_at_col(base, col)
    skipped, right = _split_at_col(rest, line_w)
    # Restore the ANSI state that was active in the base before the right portion
    restore = _active_ansi(left + skipped)
    return left + "\033[0m" + line + "\033[0m" + restore + right


def zstack(*children: Component, align: str = "top-left") -> ZStack:
    return ZStack(list(children), align=align)
