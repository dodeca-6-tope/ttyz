"""Scrollbar — data class and factory."""

from __future__ import annotations

from collections.abc import Callable

from ttyz.components.base import Node
from ttyz.components.scroll import ScrollState
from ttyz.style import dim

ScrollbarFn = Callable[[int, int, int], list[str]]


def scrollbar_default(h: int, total: int, offset: int) -> list[str]:
    """Default scrollbar: heavy line thumb with half-cell resolution, dim track."""
    if total <= h:
        return [""] * h
    h2 = h * 2
    thumb2 = max(2, h2 * h // total)
    max_off = total - h
    top2 = offset * (h2 - thumb2) // max_off if max_off > 0 else 0
    bot2 = top2 + thumb2
    return ["┃" if i * 2 < bot2 and (i + 1) * 2 > top2 else dim("│") for i in range(h)]


class Scrollbar(Node):
    """Scrollbar node."""

    __slots__ = ("state", "render_fn")
    state: ScrollState
    render_fn: ScrollbarFn


def scrollbar(
    state: ScrollState,
    render_fn: ScrollbarFn = scrollbar_default,
    width: str | None = "1",
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Scrollbar:
    node = Scrollbar((), grow if grow is not None else 1, width, height, bg, overflow)
    node.state = state
    node.render_fn = render_fn

    return node
