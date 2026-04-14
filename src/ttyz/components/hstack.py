"""Horizontal stack layout component.

Three render tiers (cheapest first):
1. Flat (C, place_at_offsets) — nested hstacks collapsed to absolute offsets.
   ASCII only; returns None → Python fallback.
2. Fast fixed (C, pad_columns) — pad + join when no leftover space and
   justify is "start". Has ASCII and ANSI-aware paths.
3. Justify (Python, _justify_row) — leftover space or non-start justify.

"""

from __future__ import annotations

from ttyz.components.base import Renderable, frame, resolve_size
from ttyz.ext import flex_distribute, pad_columns, place_at_offsets
from ttyz.measure import display_width, distribute
from ttyz.screen import pad


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


def _flex_distribute(
    act: list[Renderable], w: int, spacing: int
) -> tuple[list[int], int]:
    """Resolve column widths for children with explicit width specs."""
    n = len(act)
    col_widths = [0] * n
    weights: list[tuple[int, int]] = []
    for i in range(n):
        c = act[i]
        resolved = resolve_size(c.width, w, 0)
        col_widths[i] = c.flex_basis if resolved is None else resolved
        if c.width is None and c.grow:
            weights.append((i, c.grow))
    remaining = max(0, w - sum(col_widths) - spacing * max(0, n - 1))
    if weights:
        for (i, _), extra in zip(
            weights, distribute(remaining, [wt for _, wt in weights])
        ):
            col_widths[i] += extra
        remaining = 0
    return col_widths, remaining


def _join_rows(
    columns: list[list[str]],
    col_widths: list[int],
    remaining: int,
    spacing: int,
    justify: str,
    align: str,
) -> list[str]:
    """General multi-row join: align cells, pad, join with spacing."""
    max_rows = max((len(col) for col in columns), default=0)
    fast = remaining <= 0 and justify == "start"
    lines: list[str] = []
    for row in range(max_rows):
        cells = [_aligned_cell(col, row, max_rows, align) for col in columns]
        if fast:
            lines.append(pad_columns(cells, col_widths, spacing))
        else:
            padded = [pad(cells[i], col_widths[i]) for i in range(len(cells))]
            lines.append(_justify_row(padded, remaining, spacing, justify))
    return lines


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
            flat = c.flat_children
            if flat is not None:
                # Save remaining siblings, then descend into the flat subtree
                stack.append((nodes, i + 1, x + c.flex_basis, sp))
                stack.append((flat, 0, x, c.flat_spacing))
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

    # ── Flat path ────────────────────────────────────────────────────
    # Collapses nested fixed-width hstacks into absolute offsets, then
    # hands the list to a C function (place_at_offsets) that writes all
    # items in one memcpy pass.  Falls back to Python for non-ASCII.
    if (
        not has_grow
        and not wrap
        and justify_content == "start"
        and align_items == "start"
    ):
        flat = _try_flatten(children, spacing)
        if flat is not None:
            # Pre-render every leaf at build time — content is fixed.
            flat_items: list[tuple[int, int, str]] = [
                (off, cw, child.render(cw)[0]) for off, cw, child in flat
            ]

            def render_flat(w: int, h: int | None = None) -> list[str]:
                # C fast path: returns None when content isn't pure ASCII.
                line = place_at_offsets(flat_items)
                if line is not None:
                    return [line]
                # Python fallback for ANSI / wide-char content.
                parts: list[str] = []
                pos = 0
                for off, cw, content in flat_items:
                    if off > pos:
                        parts.append(" " * (off - pos))
                    parts.append(pad(content, cw))
                    pos = off + cw
                return ["".join(parts)]

            r = frame(Renderable(render_flat, basis), width, height, grow, bg, overflow)
            # Stored on the Renderable so a parent hstack's _try_flatten
            # can see through this node and collapse it further.
            r.flat_children = children
            r.flat_spacing = spacing
            return r

    # ── Standard path ────────────────────────────────────────────────
    # Three build-time branches — each creates a different render
    # closure so per-frame code never checks which features are active.

    if wrap:

        def render(w: int, h: int | None = None) -> list[str]:
            if not children:
                return [""]
            strs = [" ".join(c.render(w)) for c in children]
            return _wrap_chunks(strs, w, spacing)

    elif any(c.width is not None for c in act):
        # Children with explicit width specs (e.g. "50%") need the
        # Python _flex_distribute for children with explicit width specs.

        def render(w: int, h: int | None = None) -> list[str]:
            if not act:
                return [""] * h if h else [""]
            col_widths, remaining = _flex_distribute(act, w, spacing)
            columns: list[list[str]] = []
            for i, c in enumerate(act):
                cw = w if c.width is not None else col_widths[i]
                columns.append(c.render(cw, h) if c.grow else c.render(cw))
            return _join_rows(
                columns,
                col_widths,
                remaining,
                spacing,
                justify_content,
                align_items,
            )

    else:
        # Hot path (most list items land here): all children use
        # flex_basis/grow, no explicit widths.  Pre-compute the flex
        # metadata once so the per-frame render just passes two lists
        # to the C flex_distribute function.
        bases_list = [c.flex_basis for c in act]
        grows_list = [c.grow for c in act]
        start_justify = justify_content == "start" and align_items == "start"

        def render(w: int, h: int | None = None) -> list[str]:
            if not act:
                return [""] * h if h else [""]
            # C function: resolves flex distribution in one call.
            col_widths = flex_distribute(bases_list, grows_list, w, spacing)
            columns = [
                c.render(col_widths[i], h) if c.grow else c.render(col_widths[i])
                for i, c in enumerate(act)
            ]
            # When every child produces one line (the common case for
            # list rows), skip the alignment + row loop entirely and
            # hand the strings straight to the C join function.
            if start_justify and all(len(col) == 1 for col in columns):
                return [
                    pad_columns(
                        [col[0] for col in columns],
                        col_widths,
                        spacing,
                    )
                ]
            remaining = (
                0
                if has_grow
                else max(0, w - sum(col_widths) - spacing * max(0, len(act) - 1))
            )
            return _join_rows(
                columns,
                col_widths,
                remaining,
                spacing,
                justify_content,
                align_items,
            )

    return frame(Renderable(render, basis), width, height, grow, bg, overflow)
