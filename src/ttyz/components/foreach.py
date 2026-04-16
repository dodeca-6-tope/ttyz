"""Foreach component — render a list of items."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from ttyz.components.base import Node

T = TypeVar("T")


class Foreach(Node):
    """Foreach node — pre-built children from a sequence."""

    __slots__ = ()


def foreach(
    items: Sequence[T],
    render_fn: Callable[[T, int], Node],
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Foreach:
    children = tuple(render_fn(item, i) for i, item in enumerate(items))
    return Foreach(children, grow or 0, width, height, bg, overflow)
