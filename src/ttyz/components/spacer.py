"""Flexible space that expands along the major axis of its containing stack."""

from __future__ import annotations

from ttyz.components.base import Node


class Spacer(Node):
    """Flexible spacer node."""

    __slots__ = ("min_length",)
    min_length: int


def spacer(min_length: int = 0) -> Spacer:
    """Create a flexible spacer that pushes siblings apart in a stack."""
    node = Spacer((), 1)
    node.min_length = min_length
    return node
