"""Foreach component — lazily render a list of items."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from ttyz.components.base import LazyChildren, Node, Overflow

T = TypeVar("T")


class Foreach(Node):
    """Foreach node — children produced lazily from a sequence."""

    __slots__ = ()


def foreach(
    items: Sequence[T],
    render_fn: Callable[[T, int], Node],
    width: str | None = None,
    height: str | None = None,
    grow: int = 0,
    bg: int | None = None,
    overflow: Overflow = "visible",
) -> Foreach:
    return Foreach(LazyChildren(items, render_fn), grow, width, height, bg, overflow)
