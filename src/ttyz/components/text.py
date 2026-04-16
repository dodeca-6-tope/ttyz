"""Text component — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node
from ttyz.ext import TextRender


class Text(Node):
    """Text node — wraps a C ``TextRender`` callable."""

    __slots__ = ("text_render", "padding_w")
    text_render: TextRender
    padding_w: int


def text(
    value: object = "",
    *,
    wrap: bool = False,
    truncation: str | None = None,
    padding: int = 0,
    padding_left: int | None = None,
    padding_right: int | None = None,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Text:
    pl = padding if padding_left is None else padding_left
    pr = padding if padding_right is None else padding_right

    tr = TextRender(value, truncation, pl, pr, wrap)

    node = Text((), grow or 0, width, height, bg, overflow)
    node.text_render = tr
    node.padding_w = pl + pr
    return node
