"""Horizontal stack layout component — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node

_JUSTIFY_CONTENT = {"start", "end", "center", "between"}
_ALIGN_ITEMS = {"start", "end", "center"}


class HStack(Node):
    """Horizontal stack node."""

    __slots__ = ("spacing", "justify_content", "align_items", "wrap")
    spacing: int
    justify_content: str
    align_items: str
    wrap: bool


def hstack(
    *children: Node,
    spacing: int = 0,
    justify_content: str = "start",
    align_items: str = "start",
    wrap: bool = False,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> HStack:
    if justify_content not in _JUSTIFY_CONTENT:
        raise ValueError(f"unknown justify_content {justify_content!r}")
    if align_items not in _ALIGN_ITEMS:
        raise ValueError(f"unknown align_items {align_items!r}")

    node = HStack(children, grow or 0, width, height, bg, overflow)
    node.spacing = spacing
    node.justify_content = justify_content
    node.align_items = align_items
    node.wrap = wrap
    return node
