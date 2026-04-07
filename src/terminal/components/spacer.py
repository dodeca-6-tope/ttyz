"""Spacer — flexible empty space that expands along the parent's main axis."""

from __future__ import annotations

from terminal.components.base import Component


class Spacer(Component):
    def render(self, width: int, height: int | None = None) -> list[str]:
        if height is not None:
            return [""] * height
        return [" " * width]

    def flex_grow_width(self) -> int:
        return 1

    def flex_grow_height(self) -> int:
        return 1


spacer = Spacer
