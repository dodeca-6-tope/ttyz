"""List — data class, ListState, and factory."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Generic, TypeVar

from ttyz.components.base import Node
from ttyz.components.keyed import Keyed
from ttyz.components.scroll import ScrollState

T = TypeVar("T", bound=Keyed)


class ListState(Generic[T]):
    """Holds items and cursor position for a List component."""

    def __init__(self, items: builtins.list[T] | tuple[T, ...] = ()) -> None:
        self.items = builtins.list(items)
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

    def set_items(self, items: builtins.list[T] | tuple[T, ...]) -> None:
        prev = self.current.key if self.current else None
        self.items = builtins.list(items)
        if prev is not None:
            idx = next(
                (i for i, x in enumerate(self.items) if x.key == prev),
                self.cursor,
            )
            self.move_to(idx)
        else:
            self.move_to(self.cursor)

    @property
    def offset(self) -> int:
        return self.scroll.offset

    @property
    def height(self) -> int:
        return self.scroll.height

    @property
    def total(self) -> int:
        return len(self.items)


class ListView(Node):
    """List node — scrollable list with cursor selection and item cache."""

    __slots__ = ("state", "render_fn", "cache")


def list(
    state: ListState[T],
    render_fn: Callable[[T, bool], Node],
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> ListView:
    node = ListView((), grow if grow is not None else 1, width, height, bg, overflow)
    node.state = state
    node.render_fn = render_fn
    node.cache = {}

    return node
