"""ZStack — layers children on top of each other."""

from __future__ import annotations

from terminal.components.base import Renderable, frame
from terminal.measure import ANSI_RE, char_width, display_width
from terminal.screen import clip

_ALIGNMENTS = {"start", "end", "center"}
_FRAC = {"start": 0, "center": 0.5, "end": 1}


def _offsets(
    justify_content: str,
    align_items: str,
    canvas: tuple[int, int],
    layer: tuple[int, int],
) -> tuple[int, int]:
    """Compute (row_offset, col_offset) for alignment."""
    w, h = canvas
    lw, lh = layer
    vf = _FRAC.get(align_items, 0)
    hf = _FRAC.get(justify_content, 0)
    return max(0, int((h - lh) * vf)), max(0, int((w - lw) * hf))


def _active_ansi(s: str) -> str:
    """Return the ANSI state string active at the end of s."""
    if "\033" not in s:
        return ""
    codes: list[str] = []
    for m in ANSI_RE.finditer(s):
        params = m.group()[2:-1]
        if params in ("0", ""):
            codes.clear()
        else:
            codes.append(params)
    return f"\033[{';'.join(codes)}m" if codes else ""


def _split_at_col(s: str, col: int) -> tuple[str, str]:
    """Split a string at a visible column, preserving ANSI codes."""
    visible = 0
    pos = 0
    n = len(s)
    while pos < n and visible < col:
        if s[pos] == "\033" and pos + 1 < n and s[pos + 1] == "[":
            end = pos + 2
            while end < n and s[end] != "m":
                end += 1
            pos = end + 1
        else:
            visible += char_width(s[pos])
            pos += 1
    return s[:pos], s[pos:]


def _stamp(base: str, col: int, line: str, width: int) -> str:
    """Write line onto base at col, overwriting existing content."""
    max_w = width - col
    line_w = display_width(line)
    if line_w > max_w:
        line = clip(line, max_w)
        line_w = max_w
    if col == 0 and line_w >= width:
        return line
    # Pad base to width if needed
    base_w = display_width(base)
    if base_w < width:
        base = base + " " * (width - base_w)
    # Split base at visible column boundaries
    left, rest = _split_at_col(base, col)
    skipped, right = _split_at_col(rest, line_w)
    # Restore the ANSI state that was active in the base before the right portion
    restore = _active_ansi(left + skipped)
    return left + "\033[0m" + line + "\033[0m" + restore + right


def _layer_bounds(
    child: Renderable,
    layer: list[str],
    w: int,
    canvas_h: int,
    justify_content: str,
    align_items: str,
) -> tuple[int, int, int, int]:
    """Compute (row_offset, col_offset, start, end) for a layer."""
    rendered_w = max((display_width(l) for l in layer), default=0)
    layer_w = child.resolve_width(w) or rendered_w
    layer_h = child.resolve_height(canvas_h) or len(layer)
    row_off, col_off = _offsets(
        justify_content, align_items, (w, canvas_h), (layer_w, layer_h)
    )
    return row_off, col_off, max(0, -row_off), min(len(layer), canvas_h - row_off)


def zstack(
    *children: Renderable,
    justify_content: str = "start",
    align_items: str = "start",
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Renderable:
    if justify_content not in _ALIGNMENTS:
        raise ValueError(f"unknown justify_content {justify_content!r}")
    if align_items not in _ALIGNMENTS:
        raise ValueError(f"unknown align_items {align_items!r}")
    children = children

    basis = max((c.flex_basis for c in children), default=0)

    def render(w: int, h: int | None = None) -> list[str]:
        if not children:
            return [""] * h if h else [""]
        layers = [c.render(w, h) for c in children]
        canvas_h = h if h is not None else len(layers[0])
        canvas = [" " * w for _ in range(canvas_h)]
        for child, layer in zip(children, layers):
            row_off, col_off, start, end = _layer_bounds(
                child, layer, w, canvas_h, justify_content, align_items
            )
            for i in range(start, end):
                canvas[row_off + i] = _stamp(canvas[row_off + i], col_off, layer[i], w)
        return canvas

    return frame(Renderable(render, basis), width, height, grow, bg, overflow)
