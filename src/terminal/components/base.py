"""Renderable dataclass and layout helpers.

``Renderable`` is the core type — a render function plus flex properties.
``frame`` wraps a Renderable with size constraints and background.

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

RenderFn = Callable[..., list[str]]


class Renderable:
    # __slots__ over dataclass: avoids __dict__ + descriptor overhead on a hot object.
    __slots__ = ("render", "flex_basis", "grow", "width", "height")

    def __init__(
        self,
        render: RenderFn,
        flex_basis: int = 0,
        grow: int = 0,
        width: str | None = None,
        height: str | None = None,
    ) -> None:
        self.render = render
        self.flex_basis = flex_basis
        self.grow = grow
        self.width = width
        self.height = height

    def resolve_width(self, parent: int) -> int | None:
        """Resolve width spec against *parent* width. None if unspecified."""
        return _resolve(self.width, parent, 0)

    def resolve_height(self, parent: int) -> int | None:
        """Resolve height spec against *parent* height. None if unspecified."""
        return _resolve(self.height, parent, 1)


_OVERFLOW = {"visible", "hidden"}


def _clip_overflow(lines: list[str], width: int) -> list[str]:
    """Clip lines to width."""
    from terminal.screen import clip_and_pad

    return [clip_and_pad(l, width) for l in lines]


def _fit_height(lines: list[str], h: int, clips: bool) -> list[str]:
    """Truncate or pad lines to exactly h rows."""
    if clips and len(lines) > h:
        return lines[:h]
    if len(lines) < h:
        return lines + [""] * (h - len(lines))
    return lines


def frame(
    child: Renderable,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Renderable:
    """Wrap *child* with size constraints and/or background."""
    if overflow not in _OVERFLOW:
        raise ValueError(f"unknown overflow {overflow!r}")
    if width is None and height is None and bg is None and overflow == "visible":
        if grow is None:
            return child
        return Renderable(child.render, child.flex_basis, grow)

    fw = _fixed(width)
    basis = fw if fw is not None else child.flex_basis
    r_grow = grow if grow is not None else child.grow
    clips = overflow != "visible"

    def render(w: int, h: int | None = None) -> list[str]:
        rw = _resolve(width, w, 0)
        rh = _resolve(height, h, 1)
        cw = min(rw, w) if rw is not None else w
        ch = min(rh, h) if rh is not None and h is not None else (rh or h)
        lines = child.render(cw, ch)
        if rw is not None and clips:
            lines = _clip_overflow(lines, cw)
        if rh is not None:
            lines = _fit_height(lines, rh, clips)
        if bg is not None:
            lines = _apply_bg(lines, bg, cw)
        return lines

    return Renderable(render, basis, r_grow, width=width, height=height)


def _apply_bg(lines: list[str], color: int, width: int) -> list[str]:
    from terminal.screen import pad

    bg = f"\033[48;5;{color}m"
    reset = "\033[0m"
    return [
        f"{bg}{pad(line.replace(reset, reset + bg), width)}{reset}" for line in lines
    ]


def _resolve(value: str | None, parent: int | None, axis: int) -> int | None:
    if value is None:
        return None
    if value.endswith("%"):
        base = parent if parent is not None else os.get_terminal_size()[axis]
        return base * int(value[:-1]) // 100
    return int(value)


def _fixed(value: str | None) -> int | None:
    if value is None or value.endswith("%"):
        return None
    return int(value)
