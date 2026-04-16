"""Tests for Table component."""

from conftest import SnapFn

from ttyz import table, table_row, text


def test_aligns_columns(snap: SnapFn):
    tbl = table(
        table_row(text("a"), text("bb")),
        table_row(text("ccc"), text("d")),
    )
    snap(tbl, 80)


def test_single_row(snap: SnapFn):
    snap(table(table_row(text("x"), text("y"))), 80)


def test_empty(snap: SnapFn):
    snap(table(), 80)


def test_fill_column(snap: SnapFn):
    snap(table(table_row(text("id"), text("long title here", grow=1))), 30)


def test_spacing(snap: SnapFn):
    snap(table(table_row(text("a"), text("b")), spacing=3), 80)


def test_jagged_rows(snap: SnapFn):
    tbl = table(
        table_row(text("a"), text("b"), text("c")),
        table_row(text("x")),
    )
    snap(tbl, 80)


def test_multiple_fill_columns(snap: SnapFn):
    tbl = table(
        table_row(
            text("id"),
            text("name", grow=1),
            text("desc", grow=1),
        )
    )
    snap(tbl, 42)


# ── flex_grow propagation ───────────────────────────────────────────


def test_flex_grow_with_fill_column():
    tbl = table(table_row(text("id"), text("name", grow=1)))
    assert tbl.grow


def test_flex_grow_false_without_fill():
    tbl = table(table_row(text("a"), text("b")))
    assert not tbl.grow


def test_empty_row(snap: SnapFn):
    """A TableRow with zero cells should render without crashing."""
    snap(table(table_row(text("a"), text("b")), table_row()), 80)
