"""Text component — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node


class Text(Node):
    """Text node — plain data, rendering handled by C extension."""

    __slots__ = ("value", "pl", "pr", "wrap", "truncation", "_lines", "_visible_w")
    value: str
    pl: int
    pr: int
    wrap: bool
    truncation: str | None


def text(
    value: str = "",
    *,
    wrap: bool = False,
    truncation: str | None = None,
    padding: int | tuple[int, int] = 0,
    width: str | None = None,
    height: str | None = None,
    grow: int = 0,
    bg: int | None = None,
    overflow: str = "visible",
) -> Text:
    if isinstance(padding, tuple):
        pl, pr = padding
    else:
        pl = pr = padding

    node = Text((), grow, width, height, bg, overflow)
    node.value = value
    node.pl = pl
    node.pr = pr
    node.wrap = wrap
    node.truncation = truncation
    return node
