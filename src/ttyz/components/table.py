"""Table component — data class and factory."""

from __future__ import annotations

from ttyz.components.base import Node, Overflow


class TableRow:
    """A row of components for use inside a Table."""

    __slots__ = ("cells",)
    cells: list[Node]

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
    grow: int = 0,
    bg: int | None = None,
    overflow: Overflow = "visible",
) -> Table:
    rows_list = list(rows)

    node = Table((), grow, width, height, bg, overflow)
    node.rows = rows_list
    node.spacing = spacing
    return node
