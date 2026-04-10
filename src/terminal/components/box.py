"""Box component — draws a border around a child."""

from __future__ import annotations

from terminal.components.base import Renderable, frame
from terminal.components.text import Text, truncate
from terminal.measure import display_width
from terminal.screen import clip_and_pad

BORDERS: dict[str, tuple[str, str, str, str, str, str]] = {
    # (top_left, top_right, bottom_left, bottom_right, horizontal, vertical)
    "rounded": ("╭", "╮", "╰", "╯", "─", "│"),
    "normal": ("┌", "┐", "└", "┘", "─", "│"),
    "double": ("╔", "╗", "╚", "╝", "═", "║"),
    "heavy": ("┏", "┓", "┗", "┛", "━", "┃"),
}


def _top_border(style: str, title: str, inner: int) -> str:
    tl, tr, _, _, hz, _ = BORDERS[style]
    if not title:
        return f"{tl}{hz * inner}{tr}"
    label = Text(truncate(title, inner - 2, ellipsis=True))
    return f"{tl} {label} {hz * (inner - len(label) - 2)}{tr}"


def box(
    child: Renderable,
    *,
    style: str = "rounded",
    title: str = "",
    padding: int = 0,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Renderable:
    if style not in BORDERS:
        raise ValueError(f"unknown border style {style!r}")

    content_w = child.flex_basis + padding * 2
    title_w = display_width(title) + 2 if title else 0
    natural = max(content_w, title_w)
    basis = natural + 2
    grows = child.grow

    def render(w: int, h: int | None = None) -> list[str]:
        _, _, bl, br, hz, v = BORDERS[style]
        # Grow: fill available width. Fixed: clamp to natural content width.
        inner = max(0, w - 2) if grows else max(0, min(natural, w - 2))
        child_h = max(0, h - 2) if h is not None else None
        child_lines = child.render(max(0, inner - padding * 2), child_h)

        pad_str = " " * padding
        cw = inner - padding * 2
        lines = [_top_border(style, title, inner)]
        for line in child_lines:
            lines.append(f"{v}{pad_str}{clip_and_pad(line, cw)}{pad_str}{v}")
        lines.append(f"{bl}{hz * inner}{br}")
        return lines

    return frame(Renderable(render, basis, grows), width, height, grow, bg, overflow)
