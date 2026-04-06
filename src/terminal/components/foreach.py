"""Foreach component — render a list of items."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from terminal.components.base import Component

T = TypeVar("T")


class ForEach(Component):
    def __init__(self, children: list[Component]) -> None:
        self._children = children

    def flex_basis(self) -> int:
        return max((c.flex_basis() for c in self._children), default=0)

    def flex_grow_width(self) -> int:
        return max((c.flex_grow_width() for c in self._children), default=0)

    def flex_grow_height(self) -> int:
        return max((c.flex_grow_height() for c in self._children), default=0)

    def render(self, width: int, height: int | None = None) -> list[str]:
        lines: list[str] = []
        for child in self._children:
            lines.extend(child.render(width, height))
        return lines


def foreach(items: Sequence[T], render_fn: Callable[[T, int], Component]) -> ForEach:
    return ForEach([render_fn(item, i) for i, item in enumerate(items)])
