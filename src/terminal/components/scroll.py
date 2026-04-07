"""Scrollable viewport — renders only the visible children."""

from __future__ import annotations

from terminal.components.base import Component


class ScrollState:
    """Tracks scroll offset. Scroll writes resolved height/total during render."""

    def __init__(self, follow: bool = False) -> None:
        self.offset = 0
        self.height = 0
        self.total = 0
        self.follow = follow

    def scroll_up(self, n: int = 1) -> None:
        self.offset = max(0, self.offset - n)
        self.follow = False

    def scroll_down(self, n: int = 1) -> None:
        self.offset = min(self.max_offset, self.offset + n)

    def page_up(self) -> None:
        self.scroll_up(self.height)

    def page_down(self) -> None:
        self.scroll_down(self.height)

    def scroll_to_top(self) -> None:
        self.offset = 0
        self.follow = False

    def scroll_to_bottom(self) -> None:
        self.offset = self.max_offset
        self.follow = True

    def scroll_to_visible(self, index: int) -> None:
        if index < self.offset:
            self.offset = index
        elif index >= self.offset + self.height:
            self.offset = index - self.height + 1

    @property
    def max_offset(self) -> int:
        return max(0, self.total - self.height)


class Scroll(Component):
    def __init__(
        self,
        *children: Component,
        state: ScrollState,
        height: int | str = "fill",
    ) -> None:
        self._children = list(children)
        self._state = state
        self._height = height

    def flex_basis(self) -> int:
        return max((c.flex_basis() for c in self._children), default=0)

    def flex_grow_width(self) -> int:
        return 1

    def flex_grow_height(self) -> int:
        return 1 if self._height == "fill" else 0

    def render(self, width: int, height: int | None = None) -> list[str]:
        h = height if self._height == "fill" else self._height
        if not isinstance(h, int) or h <= 0:
            return []

        self._state.height = h
        self._state.total = len(self._children)
        if self._state.follow:
            self._state.offset = self._state.max_offset
        self._state.offset = max(0, min(self._state.offset, self._state.max_offset))
        if self._state.offset >= self._state.max_offset:
            self._state.follow = True

        lines: list[str] = []
        for child in self._children[self._state.offset :]:
            rendered = child.render(width)
            remaining = h - len(lines)
            if len(rendered) >= remaining:
                lines.extend(rendered[:remaining])
                break
            lines.extend(rendered)
        if len(lines) < h:
            lines.extend([""] * (h - len(lines)))

        return lines


scroll = Scroll
