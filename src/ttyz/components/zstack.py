"""ZStack — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node

_ALIGNMENTS = {"start", "end", "center"}


class ZStack(Node):
    """Z-stack node — layers children on top of each other."""

    __slots__ = ("justify_content", "align_items")
    justify_content: str
    align_items: str


def zstack(
    *children: Node,
    justify_content: str = "start",
    align_items: str = "start",
    width: str | None = None,
    height: str | None = None,
    grow: int = 0,
    bg: int | None = None,
    overflow: str = "visible",
) -> ZStack:
    if justify_content not in _ALIGNMENTS:
        raise ValueError(f"unknown justify_content {justify_content!r}")
    if align_items not in _ALIGNMENTS:
        raise ValueError(f"unknown align_items {align_items!r}")

    node = ZStack(children, grow, width, height, bg, overflow)
    node.justify_content = justify_content
    node.align_items = align_items
    return node
