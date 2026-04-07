"""Table component — columnar layout with auto-sized columns."""

from __future__ import annotations

from terminal.components.base import Component
from terminal.measure import distribute
from terminal.screen import pad


class TableRow:
    """A row of components for use inside a Table."""

    def __init__(self, *cells: Component) -> None:
        self.cells = list(cells)


class Table(Component):
    def __init__(self, *rows: TableRow, spacing: int = 1) -> None:
        self._rows = list(rows)
        self._spacing = spacing
        if rows:
            self._col_widths, self._grow_cols = self._measure_columns()
        else:
            self._col_widths, self._grow_cols = [], {}

    def _measure_columns(self) -> tuple[list[int], dict[int, int]]:
        """Return (col_widths, grow_cols) from natural sizes."""
        num_cols = max(len(r.cells) for r in self._rows)
        cells = [(ci, cell) for row in self._rows for ci, cell in enumerate(row.cells)]
        col_widths = [0] * num_cols
        grow_cols: dict[int, int] = {}
        for ci, cell in cells:
            col_widths[ci] = max(col_widths[ci], cell.flex_basis())
            g = cell.flex_grow_width()
            if g:
                grow_cols[ci] = max(grow_cols.get(ci, 0), g)
        return col_widths, grow_cols

    def _resolve_widths(self, width: int) -> list[int]:
        """Return col_widths with grow columns distributed."""
        col_widths, grow_cols = list(self._col_widths), self._grow_cols
        if grow_cols:
            gap_total = self._spacing * max(0, len(col_widths) - 1)
            fixed = (
                sum(w for ci, w in enumerate(col_widths) if ci not in grow_cols)
                + gap_total
            )
            remaining = max(0, width - fixed)
            sorted_growers = sorted(grow_cols.items())
            for (ci, _), w in zip(
                sorted_growers, distribute(remaining, [w for _, w in sorted_growers])
            ):
                col_widths[ci] = w
        return col_widths

    def render(self, width: int, height: int | None = None) -> list[str]:
        if not self._rows:
            return [""]
        col_widths = self._resolve_widths(width)
        if not col_widths:
            return [""]
        sep = " " * self._spacing
        return [_render_row(row, col_widths, sep) for row in self._rows]

    def flex_basis(self) -> int:
        if not self._rows:
            return 0
        gap_total = self._spacing * max(0, len(self._col_widths) - 1)
        return sum(self._col_widths) + gap_total

    def flex_grow_width(self) -> int:
        return max(self._grow_cols.values()) if self._grow_cols else 0


_empty = Component()


def _render_row(row: TableRow, col_widths: list[int], sep: str) -> str:
    parts: list[str] = []
    for ci, w in enumerate(col_widths):
        cell = row.cells[ci] if ci < len(row.cells) else _empty
        rendered = cell.render(w)
        content = rendered[0] if rendered else ""
        parts.append(pad(content, w))
    return sep.join(parts)


table_row = TableRow

table = Table
