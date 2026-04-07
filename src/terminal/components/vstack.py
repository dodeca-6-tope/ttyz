"""Vertical stack layout component."""

from __future__ import annotations

from terminal.components.base import Component
from terminal.components.spacer import Spacer
from terminal.measure import distribute


class VStack(Component):
    def __init__(self, *children: Component, spacing: int = 0) -> None:
        self._children = list(children)
        self._spacing = spacing

    def flex_basis(self) -> int:
        return max((c.flex_basis() for c in self._children), default=0)

    def flex_grow_width(self) -> int:
        return max(
            (c.flex_grow_width() for c in self._children if not isinstance(c, Spacer)),
            default=0,
        )

    def flex_grow_height(self) -> int:
        return max((c.flex_grow_height() for c in self._children), default=0)

    def render(self, width: int, height: int | None = None) -> list[str]:
        if height is None:
            return self._render_unconstrained(width)
        return self._render_constrained(width, height)

    def _render_unconstrained(self, width: int) -> list[str]:
        return self._join([c.render(width) for c in self._children])

    def _render_constrained(self, width: int, height: int) -> list[str]:
        weights = [
            (i, c.flex_grow_height())
            for i, c in enumerate(self._children)
            if c.flex_grow_height()
        ]
        if not weights:
            return self._render_unconstrained(width)

        grower_set = {i for i, _ in weights}
        fixed = [
            None if i in grower_set else c.render(width)
            for i, c in enumerate(self._children)
        ]
        used = self._spacing * max(0, len(self._children) - 1)
        used += sum(len(r) for r in fixed if r is not None)
        remaining = max(0, height - used)
        shares = distribute(remaining, [w for _, w in weights])
        heights = {i: h for (i, _), h in zip(weights, shares)}

        return self._join(
            [
                f if (f := fixed[i]) is not None else child.render(width, heights[i])
                for i, child in enumerate(self._children)
            ]
        )

    def _join(self, parts: list[list[str]]) -> list[str]:
        if not self._spacing:
            return [line for part in parts for line in part]
        lines: list[str] = []
        for i, part in enumerate(parts):
            if i > 0:
                lines.extend([""] * self._spacing)
            lines.extend(part)
        return lines


vstack = VStack
