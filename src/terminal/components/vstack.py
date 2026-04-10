"""Vertical stack layout component."""

from __future__ import annotations

from terminal.components.base import Renderable, frame
from terminal.measure import distribute


def _resolve_flex_heights(
    children: tuple[Renderable, ...] | list[Renderable],
    w: int,
    h: int,
    spacing: int,
) -> tuple[list[list[str] | None], dict[int, int], set[int]]:
    """Pre-render non-flex children and compute flex-grow row allocations.

    Returns (rendered, flex_heights, has_height) where rendered[i] is None
    for deferred children and flex_heights maps grow-child indices to heights.
    """
    rendered: list[list[str] | None] = []
    grow_items: list[tuple[int, int]] = []
    height_indices: list[int] = []
    used = spacing * max(0, len(children) - 1)

    for i, c in enumerate(children):
        if c.height is not None:
            height_indices.append(i)
            rh = c.resolve_height(h)
            if rh is not None:
                used += rh
            rendered.append(None)
        elif c.grow:
            grow_items.append((i, c.grow))
            rendered.append(None)
        else:
            lines = c.render(w)
            used += len(lines)
            rendered.append(lines)

    shares = distribute(max(0, h - used), [g for _, g in grow_items])
    flex_heights = {i: ht for (i, _), ht in zip(grow_items, shares)}
    return rendered, flex_heights, set(height_indices)


def _virtualize(
    children: tuple[Renderable, ...], w: int, h: int, spacing: int
) -> list[str]:
    """Render children until the viewport is full (no flex)."""
    lines: list[str] = []
    for i, child in enumerate(children):
        remaining = h - len(lines)
        if i > 0 and spacing:
            if remaining <= spacing:
                break
            lines.extend([""] * spacing)
            remaining -= spacing
        rendered = child.render(w)
        if len(rendered) >= remaining:
            lines.extend(rendered[:remaining])
            return lines
        lines.extend(rendered)
    return lines


def vstack(
    *children: Renderable,
    spacing: int = 0,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Renderable:
    basis = max((c.flex_basis for c in children), default=0)
    has_flex = any(c.grow or c.height is not None for c in children)

    def join(parts: list[list[str]]) -> list[str]:
        if not spacing:
            return [line for part in parts for line in part]
        lines: list[str] = []
        for i, part in enumerate(parts):
            if i > 0:
                lines.extend([""] * spacing)
            lines.extend(part)
        return lines

    def render(w: int, h: int | None = None) -> list[str]:
        if h is None:
            return join([c.render(w) for c in children])
        if not children:
            return [""] * h
        if not has_flex:
            return _virtualize(children, w, h, spacing)
        rendered, flex_heights, has_height = _resolve_flex_heights(
            children, w, h, spacing
        )
        return join(
            [
                f
                if (f := rendered[i]) is not None
                else child.render(w, h)
                if i in has_height
                else child.render(w, flex_heights[i])
                for i, child in enumerate(children)
            ]
        )

    return frame(Renderable(render, basis), width, height, grow, bg, overflow)
