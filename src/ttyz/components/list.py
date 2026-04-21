"""List — scrollable list with a cursor, built on ``scroll``."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Generic, TypeVar

from ttyz.components.base import LazyChildren, Node, Overflow
from ttyz.components.keyed import Keyed
from ttyz.components.scroll import Scroll, ScrollState, scroll

T = TypeVar("T", bound=Keyed)


class ListState(Generic[T]):
    """Holds items and cursor position for a List component.

    ``items`` is any ``Sequence[T]`` — a list, tuple, range, or a lazy
    custom Sequence.  No copy is made, so mutations to the underlying
    list are visible on the next render.
    """

    def __init__(self, items: Sequence[T] = ()) -> None:
        self.items: Sequence[T] = items
        self.cursor = 0
        self.scroll = ScrollState()

    @property
    def current(self) -> T | None:
        return self.items[self.cursor] if self.items else None

    def clamp(self, index: int) -> int:
        return max(0, min(index, self.total - 1)) if self.total else 0

    def move(self, delta: int) -> None:
        self.cursor = self.clamp(self.cursor + delta)

    def move_to(self, index: int) -> None:
        self.cursor = self.clamp(index)

    def set_items(self, items: Sequence[T]) -> None:
        prev = self.current.key if self.current else None
        self.items = items
        idx = (
            next((i for i, x in enumerate(items) if x.key == prev), self.cursor)
            if prev is not None
            else self.cursor
        )
        self.move_to(idx)

    @property
    def offset(self) -> int:
        return self.scroll.offset

    @property
    def height(self) -> int:
        return self.scroll.height

    @property
    def total(self) -> int:
        return len(self.items)


def list(
    state: ListState[T],
    render_fn: Callable[[T, bool], Node],
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: Overflow = "visible",
) -> Scroll:
    state.cursor = state.clamp(state.cursor)
    state.scroll.scroll_to_visible(state.cursor)
    return scroll(
        LazyChildren(
            state.items,
            lambda item, i: render_fn(item, i == state.cursor),
        ),
        state=state.scroll,
        width=width,
        height=height,
        grow=grow,
        bg=bg,
        overflow=overflow,
    )
