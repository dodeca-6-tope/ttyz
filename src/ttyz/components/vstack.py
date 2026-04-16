"""Vertical stack layout component — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node


class VStack(Node):
    """Vertical stack node."""

    __slots__ = ("spacing", "has_flex")
    spacing: int
    has_flex: bool


def vstack(
    *children: Node,
    spacing: int = 0,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> VStack:
    has_flex = any(c.grow or c.height is not None for c in children)

    node = VStack(children, grow or 0, width, height, bg, overflow)
    node.spacing = spacing
    node.has_flex = has_flex
    return node
