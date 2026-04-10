"""Table component — columnar layout with auto-sized columns."""

from __future__ import annotations

from terminal.components.base import Renderable, frame
from terminal.measure import distribute
from terminal.screen import pad


class TableRow:
    """A row of components for use inside a Table."""

    def __init__(self, *cells: Renderable) -> None:
        self.cells = list(cells)


def _empty_render(w: int, h: int | None = None) -> list[str]:
    return [""]


_EMPTY_CELL = Renderable(_empty_render)


def _measure_columns(rows: list[TableRow]) -> tuple[list[int], dict[int, int]]:
    """Return (col_widths, grow_cols) from natural sizes."""
    num_cols = max(len(r.cells) for r in rows)
    cells = [(ci, cell) for row in rows for ci, cell in enumerate(row.cells)]
    col_widths = [0] * num_cols
    grow_cols: dict[int, int] = {}
    for ci, cell in cells:
        col_widths[ci] = max(col_widths[ci], cell.flex_basis)
        g = cell.grow
        if g:
            grow_cols[ci] = max(grow_cols.get(ci, 0), g)
    return col_widths, grow_cols


def _resolve_widths(
    base_widths: list[int], grow_cols: dict[int, int], spacing: int, width: int
) -> list[int]:
    """Return column widths with grow columns distributed."""
    if not grow_cols:
        return list(base_widths)
    result = list(base_widths)
    gap_total = spacing * max(0, len(result) - 1)
    fixed = sum(w for ci, w in enumerate(result) if ci not in grow_cols) + gap_total
    remaining = max(0, width - fixed)
    sorted_growers = sorted(grow_cols.items())
    for (ci, _), w in zip(
        sorted_growers, distribute(remaining, [w for _, w in sorted_growers])
    ):
        result[ci] = w
    return result


def _render_row(row: TableRow, col_widths: list[int], sep: str) -> str:
    parts: list[str] = []
    for ci, w in enumerate(col_widths):
        cell = row.cells[ci] if ci < len(row.cells) else _EMPTY_CELL
        rendered = cell.render(w)
        content = rendered[0] if rendered else ""
        parts.append(pad(content, w))
    return sep.join(parts)


table_row = TableRow


def table(
    *rows: TableRow,
    spacing: int = 1,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Renderable:
    rows_list = list(rows)

    if rows_list:
        col_widths, grow_cols = _measure_columns(rows_list)
        basis = sum(col_widths) + spacing * max(0, len(col_widths) - 1)
    else:
        col_widths, grow_cols = [], {}
        basis = 0

    r_grow = max(grow_cols.values()) if grow_cols else 0

    def render(w: int, h: int | None = None) -> list[str]:
        if not rows_list:
            return [""]
        resolved = _resolve_widths(col_widths, grow_cols, spacing, w)
        if not resolved:
            return [""]
        sep = " " * spacing
        visible = rows_list if h is None else rows_list[:h]
        return [_render_row(row, resolved, sep) for row in visible]

    return frame(Renderable(render, basis, r_grow), width, height, grow, bg, overflow)
