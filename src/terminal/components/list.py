"""List — scrollable list with cursor selection."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Generic, TypeVar

from terminal.components.base import Component
from terminal.components.keyed import Keyed
from terminal.components.scroll import ScrollState

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


class List(Component, Generic[T]):
    """Scrollable list that only builds visible children at render time."""

    def __init__(
        self,
        state: ListState[T],
        render_fn: Callable[[T, bool], Component],
        *,
        height: int | str = "fill",
    ) -> None:
        self._state = state
        self._render_fn = render_fn
        self._height = height

    def flex_grow_width(self) -> int:
        return 1

    def flex_grow_height(self) -> int:
        return 1 if self._height == "fill" else 0

    def render(self, width: int, height: int | None = None) -> builtins.list[str]:
        state = self._state
        state.cursor = state.clamp(state.cursor)
        state.scroll.scroll_to_visible(state.cursor)

        h = height if self._height == "fill" else self._height
        if not isinstance(h, int) or h <= 0:
            return []

        total = state.total
        state.scroll.height = h
        state.scroll.total = total
        state.scroll.offset = max(0, min(state.scroll.offset, state.scroll.max_offset))
        offset = state.scroll.offset

        lines: builtins.list[str] = []
        for i in range(offset, total):
            child = self._render_fn(state.items[i], i == state.cursor)
            rendered = child.render(width)
            remaining = h - len(lines)
            if len(rendered) >= remaining:
                lines.extend(rendered[:remaining])
                break
            lines.extend(rendered)
        if len(lines) < h:
            lines.extend([""] * (h - len(lines)))
        return lines


list = List
