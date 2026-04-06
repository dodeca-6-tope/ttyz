"""Horizontal stack layout component."""

from __future__ import annotations

from terminal.components.base import Component
from terminal.components.spacer import Spacer
from terminal.measure import display_width, distribute
from terminal.screen import pad


def _wrap_chunks(strs: list[str], width: int, gap: int) -> list[str]:
    sep = " " * gap
    lines: list[str] = []
    line: list[str] = []
    line_w = 0
    for s in strs:
        s_w = display_width(s)
        needed = line_w + gap + s_w if line else s_w
        if needed > width and line:
            lines.append(sep.join(line))
            line, line_w = [s], s_w
            continue
        line.append(s)
        line_w = needed
    if line:
        lines.append(sep.join(line))
    return lines


class HStack(Component):
    def __init__(
        self,
        children: list[Component],
        *,
        spacing: int = 0,
        justify: str = "start",
        wrap: bool = False,
    ) -> None:
        _JUSTIFY = {"start", "end", "center", "between"}
        if justify not in _JUSTIFY:
            raise ValueError(f"unknown justify {justify!r}")
        self._children = children
        self._spacing = spacing
        self._justify = justify
        self._wrap = wrap

    def _active(self) -> list[Component]:
        return [c for c in self._children if c.flex_basis() > 0 or c.flex_grow_width()]

    def render(self, width: int, height: int | None = None) -> list[str]:
        if self._wrap:
            return self._render_wrap(width)
        return self._render_fixed(width, height)

    def _render_wrap(self, width: int) -> list[str]:
        if not self._children:
            return [""]
        strs = [" ".join(c.render(width)) for c in self._children]
        return _wrap_chunks(strs, width, self._spacing)

    def _render_fixed(self, width: int, height: int | None = None) -> list[str]:
        active = self._active()
        if not active:
            return [""]

        col_widths = [c.flex_basis() for c in active]
        weights = [
            (i, c.flex_grow_width())
            for i, c in enumerate(active)
            if c.flex_grow_width()
        ]
        gap_total = self._spacing * max(0, len(active) - 1)
        remaining = max(0, width - sum(col_widths) - gap_total)

        if weights:
            for (i, _), extra in zip(
                weights, distribute(remaining, [w for _, w in weights])
            ):
                col_widths[i] += extra
            remaining = 0

        columns = [
            c.render(col_widths[i], height)
            if c.flex_grow_height()
            else c.render(col_widths[i])
            for i, c in enumerate(active)
        ]
        max_rows = max((len(col) for col in columns), default=0)

        lines: list[str] = []
        for row in range(max_rows):
            cells: list[str] = []
            for i, col in enumerate(columns):
                cell = col[row] if row < len(col) else ""
                cells.append(pad(cell, col_widths[i]))
            lines.append(self._justify_row(cells, remaining))
        return lines

    def _justify_row(self, cells: list[str], remaining: int) -> str:
        gap = " " * self._spacing
        joined = gap.join(cells)

        if remaining <= 0 or self._justify == "start":
            return joined
        if self._justify == "end":
            return " " * remaining + joined
        if self._justify == "center":
            return " " * (remaining // 2) + joined
        if self._justify == "between" and len(cells) > 1:
            return self._justify_between(cells, remaining)
        return joined

    def _justify_between(self, cells: list[str], remaining: int) -> str:
        gaps = len(cells) - 1
        per_gap = remaining // gaps
        extra = remaining % gaps
        parts: list[str] = []
        for i, cell in enumerate(cells):
            parts.append(cell)
            if i < gaps:
                parts.append(" " * (self._spacing + per_gap + (1 if i < extra else 0)))
        return "".join(parts)

    def flex_basis(self) -> int:
        active = self._active()
        gap_total = self._spacing * max(0, len(active) - 1)
        return sum(c.flex_basis() for c in active) + gap_total

    def flex_grow_width(self) -> int:
        child_max = max((c.flex_grow_width() for c in self._children), default=0)
        if self._justify != "start":
            return max(1, child_max)
        return child_max

    def flex_grow_height(self) -> int:
        return max(
            (c.flex_grow_height() for c in self._children if not isinstance(c, Spacer)),
            default=0,
        )


def hstack(
    *children: Component,
    spacing: int = 0,
    justify: str = "start",
    wrap: bool = False,
) -> HStack:
    return HStack(list(children), spacing=spacing, justify=justify, wrap=wrap)
