"""Tests for Table component."""

from helpers import vis

from terminal import table, table_row, text


def test_aligns_columns():
    tbl = table(
        table_row(text("a"), text("bb")),
        table_row(text("ccc"), text("d")),
    )
    assert vis(tbl.render(80)) == [
        "a···bb",
        "ccc·d·",
    ]


def test_single_row():
    assert vis(table(table_row(text("x"), text("y"))).render(80)) == ["x·y"]


def test_empty():
    assert vis(table().render(80)) == [""]


def test_fill_column():
    tbl = table(table_row(text("id"), text("long title here", grow=1)))
    lines = vis(tbl.render(30))
    assert len(lines[0]) <= 30


def test_spacing():
    assert vis(table(table_row(text("a"), text("b")), spacing=3).render(80)) == [
        "a···b",
    ]


def test_jagged_rows():
    tbl = table(
        table_row(text("a"), text("b"), text("c")),
        table_row(text("x")),
    )
    lines = vis(tbl.render(80))
    assert lines == [
        "a·b·c",
        "x····",
    ]


def test_multiple_fill_columns():
    tbl = table(
        table_row(
            text("id"),
            text("name", grow=1),
            text("desc", grow=1),
        )
    )
    assert vis(tbl.render(42)) == [
        "id·name················desc···············",
    ]


# ── flex_grow propagation ───────────────────────────────────────────


def test_flex_grow_with_fill_column():
    tbl = table(table_row(text("id"), text("name", grow=1)))
    assert tbl.grow


def test_flex_grow_false_without_fill():
    tbl = table(table_row(text("a"), text("b")))
    assert not tbl.grow
