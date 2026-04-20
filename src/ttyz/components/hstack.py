"""Horizontal stack layout component — data class and factory."""

from __future__ import annotations

from collections.abc import Sequence

from ttyz.components.base import Align, Justify, Node, Overflow, resolve_children


class HStack(Node):
    """Horizontal stack node."""

    __slots__ = ("spacing", "justify_content", "align_items", "wrap")
    spacing: int
    justify_content: Justify
    align_items: Align
    wrap: bool


def hstack(
    *children: Node | Sequence[Node],
    spacing: int = 0,
    justify_content: Justify = "start",
    align_items: Align = "start",
    wrap: bool = False,
    width: str | None = None,
    height: str | None = None,
    grow: int = 0,
    bg: int | None = None,
    overflow: Overflow = "visible",
) -> HStack:
    node = HStack(resolve_children(children), grow, width, height, bg, overflow)
    node.spacing = spacing
    node.justify_content = justify_content
    node.align_items = align_items
    node.wrap = wrap
    return node
