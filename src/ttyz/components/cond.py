"""Conditional rendering component."""

from __future__ import annotations

from ttyz.components.base import Node


class Cond(Node):
    """Conditional node — renders child when present, empty otherwise."""

    __slots__ = ()


def cond(
    condition: object,
    child: Node,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Node:
    if not condition:
        return Node()

    if (
        width is None
        and height is None
        and bg is None
        and overflow == "visible"
        and (grow is None or grow == child.grow)
    ):
        return child

    return Cond(
        (child,),
        grow if grow is not None else child.grow,
        width,
        height,
        bg,
        overflow,
    )
