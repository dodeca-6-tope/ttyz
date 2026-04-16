"""Scrollable viewport — data class, ScrollState, and factory."""

from __future__ import annotations

from ttyz.components.base import Node


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


class Scroll(Node):
    """Scrollable viewport node."""

    __slots__ = ("state",)
    state: ScrollState


def scroll(
    *children: Node,
    state: ScrollState,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Scroll:
    node = Scroll(
        children, grow if grow is not None else 1, width, height, bg, overflow
    )
    node.state = state

    return node
