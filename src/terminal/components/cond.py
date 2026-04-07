"""Conditional rendering component."""

from __future__ import annotations

from terminal.components.base import Component


class Cond(Component):
    def __init__(self, condition: object, child: Component) -> None:
        self._condition = bool(condition)
        self._child = child

    def flex_basis(self) -> int:
        return self._child.flex_basis() if self._condition else 0

    def flex_grow_width(self) -> int:
        return self._child.flex_grow_width() if self._condition else 0

    def flex_grow_height(self) -> int:
        return self._child.flex_grow_height() if self._condition else 0

    def render(self, width: int, height: int | None = None) -> list[str]:
        if self._condition:
            return self._child.render(width, height)
        return []


cond = Cond
