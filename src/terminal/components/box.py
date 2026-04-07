"""Box component — draws a border around a child."""

from __future__ import annotations

from terminal.components.base import Component
from terminal.components.text import Text
from terminal.measure import display_width
from terminal.screen import clip

BORDERS: dict[str, tuple[str, str, str, str, str, str]] = {
    # (top_left, top_right, bottom_left, bottom_right, horizontal, vertical)
    "rounded": ("╭", "╮", "╰", "╯", "─", "│"),
    "normal": ("┌", "┐", "└", "┘", "─", "│"),
    "double": ("╔", "╗", "╚", "╝", "═", "║"),
    "heavy": ("┏", "┓", "┗", "┛", "━", "┃"),
}


class Box(Component):
    def __init__(
        self,
        child: Component,
        *,
        style: str = "rounded",
        title: str = "",
        padding: int = 0,
    ) -> None:
        if style not in BORDERS:
            raise ValueError(f"unknown border style {style!r}")
        self._child = child
        self._style = style
        self._title = title
        self._padding = padding

    def flex_basis(self) -> int:
        content_w = self._child.flex_basis() + self._padding * 2
        title_w = display_width(self._title) + 2 if self._title else 0
        return max(content_w, title_w) + 2

    def flex_grow_width(self) -> int:
        return self._child.flex_grow_width()

    def flex_grow_height(self) -> int:
        return self._child.flex_grow_height()

    def render(self, width: int, height: int | None = None) -> list[str]:
        _, _, bl, br, hz, v = BORDERS[self._style]
        pad = self._padding
        inner = self._inner_width(width)
        child_h = max(0, height - 2) if height is not None else None
        child_lines = self._child.render(max(0, inner - pad * 2), child_h)

        top = self._top_border(inner)
        pad_str = " " * pad
        lines = [top]
        content_w = inner - pad * 2
        for line in child_lines:
            w = display_width(line)
            if w > content_w:
                line = clip(line, content_w)
                w = content_w
            gap = inner - w - pad * 2
            lines.append(f"{v}{pad_str}{line}{' ' * gap}{pad_str}{v}")
        lines.append(f"{bl}{hz * inner}{br}")
        return lines

    def _inner_width(self, width: int) -> int:
        if self._child.flex_grow_width():
            return max(0, width - 2)
        pad = self._padding
        content_w = self._child.flex_basis() + pad * 2
        title_w = display_width(self._title) + 2 if self._title else 0
        return max(0, min(max(content_w, title_w), width - 2))

    def _top_border(self, inner: int) -> str:
        tl, tr, _, _, hz, _ = BORDERS[self._style]
        if not self._title:
            return f"{tl}{hz * inner}{tr}"
        label = Text(self._title, max_width=inner - 2, ellipsis=True)
        return f"{tl} {label} {hz * (inner - len(label) - 2)}{tr}"


box = Box
