"""Vertical stack layout component — data class and factory."""

from __future__ import annotations

from collections.abc import Sequence

from ttyz.components.base import Node, Overflow, resolve_children


class VStack(Node):
    """Vertical stack node."""

    __slots__ = ("spacing", "has_flex")
    spacing: int
    has_flex: bool


def vstack(
    *children: Node | Sequence[Node],
    spacing: int = 0,
    width: str | None = None,
    height: str | None = None,
    grow: int = 0,
    bg: int | None = None,
    overflow: Overflow = "visible",
) -> VStack:
    backing = resolve_children(children)
    # Only probe has_flex for varargs (tuple from resolve).  A Sequence
    # backing is potentially huge or lazy; iterating it here would defeat
    # the point.  Assume non-flex — that's also the path where lazy
    # children actually work (the render loop can short-circuit on h).
    if isinstance(backing, tuple):
        has_flex = any(c.grow or c.height is not None for c in backing)
    else:
        has_flex = False

    node = VStack(backing, grow, width, height, bg, overflow)
    node.spacing = spacing
    node.has_flex = has_flex
    return node
