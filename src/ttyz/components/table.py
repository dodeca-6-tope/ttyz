"""Table component — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node


class TableRow:
    """A row of components for use inside a Table."""

    def __init__(self, *cells: Node) -> None:
        self.cells = list(cells)


table_row = TableRow


class Table(Node):
    """Table node — columnar layout."""

    __slots__ = ("rows", "spacing")
    rows: list[TableRow]
    spacing: int


def table(
    *rows: TableRow,
    spacing: int = 1,
    width: str | None = None,
    height: str | None = None,
    grow: int | None = None,
    bg: int | None = None,
    overflow: str = "visible",
) -> Table:
    rows_list = list(rows)
    r_grow = max((c.grow for r in rows_list for c in r.cells), default=0)

    node = Table((), grow if grow is not None else r_grow, width, height, bg, overflow)
    node.rows = rows_list
    node.spacing = spacing
    return node
