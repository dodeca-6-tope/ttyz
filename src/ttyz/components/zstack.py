"""ZStack — data class and factory."""

from __future__ import annotations

from collections.abc import Sequence

from ttyz.components.base import Align, Node, Overflow, resolve_children


class ZStack(Node):
    """Z-stack node — layers children on top of each other."""

    __slots__ = ("justify_content", "align_items")
    justify_content: Align
    align_items: Align


def zstack(
    *children: Node | Sequence[Node],
    justify_content: Align = "start",
    align_items: Align = "start",
    width: str | None = None,
    height: str | None = None,
    grow: int = 0,
    bg: int | None = None,
    overflow: Overflow = "visible",
) -> ZStack:
    node = ZStack(resolve_children(children), grow, width, height, bg, overflow)
    node.justify_content = justify_content
    node.align_items = align_items
    return node
