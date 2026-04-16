"""Box component — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node

BORDERS: dict[str, tuple[str, str, str, str, str, str]] = {
    # (top_left, top_right, bottom_left, bottom_right, horizontal, vertical)
    "rounded": ("╭", "╮", "╰", "╯", "─", "│"),
    "normal": ("┌", "┐", "└", "┘", "─", "│"),
    "double": ("╔", "╗", "╚", "╝", "═", "║"),
    "heavy": ("┏", "┓", "┗", "┛", "━", "┃"),
}


class Box(Node):
    """Box node — border around a single child."""

    __slots__ = ("style", "title", "padding")
    style: str
    title: str
    padding: int


def box(
    child: Node,
    *,
    style: str = "rounded",
    title: str = "",
    padding: int = 0,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Box:
    if style not in BORDERS:
        raise ValueError(f"unknown border style {style!r}")

    node = Box(
        (child,),
        grow if grow is not None else child.grow,
        width,
        height,
        bg,
        overflow,
    )
    node.style = style
    node.title = title
    node.padding = padding
    return node
