"""Tests for component composability — any nesting should work."""

from conftest import SnapFn

from ttyz import (
    bold,
    color,
    cond,
    foreach,
    hstack,
    table,
    table_row,
    text,
    vstack,
)


def test_vstack_in_hstack(snap: SnapFn):
    snap(hstack(vstack(text("a"), text("b")), text("c"), spacing=1), 20)


def test_hstack_in_vstack(snap: SnapFn):
    snap(vstack(hstack(text("a"), text("b"), spacing=1), text("c")), 20)


def test_table_in_vstack(snap: SnapFn):
    snap(vstack(text(bold("header")), table(table_row(text("x"), text("y")))), 80)


def test_foreach_in_hstack(snap: SnapFn):
    fe = foreach(["a", "b"], lambda x, i: text(x))
    snap(hstack(fe, text("side"), spacing=2), 30)


def test_cond_in_hstack_between(snap: SnapFn):
    snap(hstack(cond(False, text("L")), text("R"), justify_content="between"), 20)


def test_deeply_nested(snap: SnapFn):
    tree = vstack(
        hstack(text("title"), text("v1.0"), justify_content="between"),
        table(table_row(text(">"), text("item"), text(color(2, "ok")))),
        hstack(text("[q] quit"), text("[h] help"), wrap=True, spacing=2),
    )
    snap(tree, 60)
