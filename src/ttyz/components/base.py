"""Renderable dataclass and layout helpers.

``Renderable`` is the core type — a render function plus flex properties.

When constructed with size constraints (width/height), background, or
overflow, the render function is wrapped automatically.

Accepted size values (width / height):
    None       — no constraint (default)
    "50%"      — percentage of the parent dimension (falls back to
                 terminal size when no parent is available)
    "28"       — fixed number of columns / rows

``grow`` is separate from size — it maps to CSS ``flex-grow`` and controls
how remaining space is distributed among siblings in a flex container.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeAlias

from ttyz.screen import clip_and_pad, pad

RenderFn: TypeAlias = Callable[..., list[str]]


def _clip_overflow(lines: list[str], width: int) -> list[str]:
    return [clip_and_pad(l, width) for l in lines]


def _fit_height(lines: list[str], h: int, clips: bool) -> list[str]:
    if clips and len(lines) > h:
        return lines[:h]
    if len(lines) < h:
        return lines + [""] * (h - len(lines))
    return lines


class Renderable:
    """Render function plus flex layout properties."""

    __slots__ = (
        "render",
        "flex_basis",
        "grow",
        "width",
        "height",
        "flat_children",
        "flat_spacing",
    )

    def __init__(
        self,
        render: RenderFn,
        flex_basis: int = 0,
        grow: int = 0,
        width: str | None = None,
        height: str | None = None,
        bg: int | None = None,
        overflow: str = "visible",
    ) -> None:
        if overflow not in ("visible", "hidden"):
            raise ValueError(f"unknown overflow {overflow!r}")

        if width is not None and not width.endswith("%"):
            flex_basis = int(width)

        if (
            width is not None
            or height is not None
            or bg is not None
            or overflow != "visible"
        ):
            clips = overflow != "visible"
            inner = render

            def _framed(w: int, h: int | None = None) -> list[str]:
                rw = resolve_size(width, w, 0)
                rh = resolve_size(height, h, 1)
                cw = min(rw, w) if rw is not None else w
                ch = min(rh, h) if rh is not None and h is not None else (rh or h)
                lines = inner(cw, ch)
                if rw is not None and clips:
                    lines = _clip_overflow(lines, cw)
                target_h = rh
                if target_h is None and bg is not None:
                    target_h = ch
                if target_h is not None:
                    lines = _fit_height(lines, target_h, clips)
                if bg is not None:
                    lines = _apply_bg(lines, bg, cw)
                return lines

            render = _framed

        self.render = render
        self.flex_basis = flex_basis
        self.grow = grow
        self.width = width
        self.height = height
        self.flat_children: tuple[Renderable, ...] | None = None
        self.flat_spacing: int = 0


def _apply_bg(lines: list[str], color: int, width: int) -> list[str]:
    bg = f"\033[48;5;{color}m"
    reset = "\033[0m"
    return [
        f"{bg}{pad(line.replace(reset, reset + bg), width)}{reset}" for line in lines
    ]


def resolve_size(value: str | None, parent: int | None, axis: int) -> int | None:
    if value is None:
        return None
    if value.endswith("%"):
        base = parent if parent is not None else os.get_terminal_size()[axis]
        return base * int(value[:-1]) // 100
    return int(value)
