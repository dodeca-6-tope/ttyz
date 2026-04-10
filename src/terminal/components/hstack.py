"""Horizontal stack layout component.

Three render tiers (cheapest first):
1. Flat (C, render_flat_line) — nested hstacks collapsed to absolute offsets.
   ASCII only; returns None → Python fallback.
2. Fast fixed (C, hstack_join_row) — pad + join when no leftover space and
   justify is "start". Has ASCII and ANSI-aware paths.
3. Justify (Python, _justify_row) — leftover space or non-start justify.

"""

from __future__ import annotations

from terminal.buffer import hstack_join_row, render_flat_line
from terminal.components.base import Renderable, frame
from terminal.measure import display_width, distribute
from terminal.screen import pad


def _wrap_chunks(strs: list[str], width: int, gap: int) -> list[str]:
    sep = " " * gap
    lines: list[str] = []
    line: list[str] = []
    line_w = 0
    for s in strs:
        s_w = display_width(s)
        needed = line_w + gap + s_w if line else s_w
        if needed > width and line:
            lines.append(sep.join(line))
            line, line_w = [s], s_w
            continue
        line.append(s)
        line_w = needed
    if line:
        lines.append(sep.join(line))
    return lines


_JUSTIFY_CONTENT = {"start", "end", "center", "between"}
_ALIGN_ITEMS = {"start", "end", "center"}


def _aligned_cell(col: list[str], row: int, max_rows: int, align: str) -> str:
    if align == "end":
        offset = max_rows - len(col)
        return col[row - offset] if row >= offset else ""
    if align == "center":
        offset = (max_rows - len(col)) // 2
        return col[row - offset] if offset <= row < offset + len(col) else ""
    return col[row] if row < len(col) else ""


def _justify_row(cells: list[str], remaining: int, spacing: int, mode: str) -> str:
    gap = " " * spacing
    joined = gap.join(cells)
    if remaining <= 0 or mode == "start":
        return joined
    if mode == "end":
        return " " * remaining + joined
    if mode == "center":
        return " " * (remaining // 2) + joined
    if mode == "between" and len(cells) > 1:
        extras = distribute(remaining, [1] * (len(cells) - 1))
        sep = [" " * (spacing + e) for e in extras]
        return "".join(c + s for c, s in zip(cells, sep)) + cells[-1]
    return joined


def _resolve_col_widths(
    act: list[Renderable], w: int, spacing: int
) -> tuple[list[int], int]:
    """Resolve column widths and leftover space for flex-grow distribution.

    Index loop + local caching over enumerate/comprehensions — called per
    frame per hstack, overhead adds up at 60 fps.
    """
    n = len(act)
    col_widths = [0] * n
    weights: list[tuple[int, int]] = []
    for i in range(n):
        c = act[i]
        cw = c.width
        if cw is not None:
            col_widths[i] = c.resolve_width(w) or c.flex_basis
        else:
            col_widths[i] = c.flex_basis
            g = c.grow
            if g:
                weights.append((i, g))
    remaining = max(0, w - sum(col_widths) - spacing * max(0, n - 1))
    if weights:
        for (i, _), extra in zip(
            weights, distribute(remaining, [wt for _, wt in weights])
        ):
            col_widths[i] += extra
        remaining = 0
    return col_widths, remaining


def _render_columns(
    act: list[Renderable], col_widths: list[int], w: int, h: int | None
) -> list[list[str]]:
    """Render each child at its resolved column width."""
    columns: list[list[str]] = []
    for i, c in enumerate(act):
        cw = w if c.width is not None else col_widths[i]
        columns.append(c.render(cw, h) if c.grow else c.render(cw))
    return columns


# ── Flat layout helpers ──────────────────────────────────────────────


def _try_flatten(
    children: tuple[Renderable, ...], spacing: int
) -> list[tuple[int, int, Renderable]] | None:
    """Flatten a tree of fixed-width, single-line hstacks into (offset, width, leaf) triples.

    Returns None if any child uses grow, explicit width, or multi-line content.
    """
    items: list[tuple[int, int, Renderable]] = []
    # Stack of (nodes, index, x_offset, spacing) for iterative traversal
    stack: list[tuple[tuple[Renderable, ...] | list[Renderable], int, int, int]] = [
        (children, 0, 0, spacing)
    ]
    while stack:
        nodes, idx, x, sp = stack.pop()
        for i in range(idx, len(nodes)):
            c = nodes[i]
            if i > 0 and sp:
                x += sp
            flat = getattr(c.render, "flat_children", None)
            if flat is not None:
                # Save remaining siblings, then descend into the flat subtree
                stack.append((nodes, i + 1, x, sp))
                stack.append((flat, 0, x, getattr(c.render, "flat_spacing", 0)))
                break
            if c.grow or c.width is not None:
                return None
            probe = c.render(c.flex_basis)
            if len(probe) != 1:
                return None
            items.append((x, c.flex_basis, c))
            x += c.flex_basis
    return items


# ── hstack ───────────────────────────────────────────────────────────


def hstack(
    *children: Renderable,
    spacing: int = 0,
    justify_content: str = "start",
    align_items: str = "start",
    wrap: bool = False,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Renderable:
    if justify_content not in _JUSTIFY_CONTENT:
        raise ValueError(f"unknown justify_content {justify_content!r}")
    if align_items not in _ALIGN_ITEMS:
        raise ValueError(f"unknown align_items {align_items!r}")
    # Single pass: filter active children, detect grow.
    act: list[Renderable] = []
    has_grow = False
    basis = 0
    for c in children:
        if not (c.flex_basis > 0 or c.grow or c.width is not None):
            continue
        act.append(c)
        basis += c.flex_basis
        if c.grow:
            has_grow = True

    basis += spacing * max(0, len(act) - 1)

    # ── Flat path (see module docstring, tier 1) ─────────────────────
    if (
        not has_grow
        and not wrap
        and justify_content == "start"
        and align_items == "start"
    ):
        flat = _try_flatten(children, spacing)
        if flat is not None:
            flat_items: list[tuple[int, int, str]] = [
                (off, cw, child.render(cw)[0]) for off, cw, child in flat
            ]

            def render_flat(w: int, h: int | None = None) -> list[str]:
                line = render_flat_line(flat_items)  # None → non-ASCII/ANSI, fall back
                if line is None:
                    parts: list[str] = []
                    pos = 0
                    for off, cw, content in flat_items:
                        if off > pos:
                            parts.append(" " * (off - pos))
                        parts.append(content)
                        gap = cw - display_width(content)
                        if gap > 0:
                            parts.append(" " * gap)
                        pos = off + cw
                    return ["".join(parts)]
                return [line]

            # Expose tree structure so a parent hstack's _try_flatten can
            # see through this node and collapse it into the flat list.
            render_flat.flat_children = children  # type: ignore[attr-defined]
            render_flat.flat_spacing = spacing  # type: ignore[attr-defined]
            return frame(
                Renderable(render_flat, basis), width, height, grow, bg, overflow
            )

    # ── Standard path ────────────────────────────────────────────────

    if wrap:

        def render(w: int, h: int | None = None) -> list[str]:
            if not children:
                return [""]
            strs = [" ".join(c.render(w)) for c in children]
            return _wrap_chunks(strs, w, spacing)

    else:

        def render(w: int, h: int | None = None) -> list[str]:
            if not act:
                return [""] * h if h else [""]

            col_widths, remaining = _resolve_col_widths(act, w, spacing)
            columns = _render_columns(act, col_widths, w, h)
            max_rows = max((len(col) for col in columns), default=0)
            # No leftover space + start-justify → skip Python padding, use C path (tier 2).
            fast = remaining <= 0 and justify_content == "start"

            lines: list[str] = []
            for row in range(max_rows):
                cells = [
                    _aligned_cell(col, row, max_rows, align_items) for col in columns
                ]
                if fast:
                    lines.append(hstack_join_row(cells, col_widths, spacing))
                else:
                    padded = [pad(cells[i], col_widths[i]) for i in range(len(cells))]
                    lines.append(
                        _justify_row(padded, remaining, spacing, justify_content)
                    )
            return lines

    return frame(Renderable(render, basis), width, height, grow, bg, overflow)
