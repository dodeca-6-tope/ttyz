"""Tests for component composability — any nesting should work."""

from helpers import vis

from terminal import (
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


def test_vstack_in_hstack():
    assert vis(hstack(vstack(text("a"), text("b")), text("c"), spacing=1).render(20)) == [
        "a·c",
        "b··",
    ]


def test_hstack_in_vstack():
    assert vis(vstack(hstack(text("a"), text("b"), spacing=1), text("c")).render(20)) == [
        "a·b",
        "c",
    ]


def test_table_in_vstack():
    assert vis(
        vstack(text(bold("header")), table(table_row(text("x"), text("y")))).render(80)
    ) == [
        "header",
        "x·y",
    ]


def test_foreach_in_hstack():
    fe = foreach(["a", "b"], lambda x, i: text(x))
    assert vis(hstack(fe, text("side"), spacing=2).render(30)) == [
        "a··side",
        "b······",
    ]


def test_cond_in_hstack_between():
    assert vis(
        hstack(cond(False, text("L")), text("R"), justify_content="between").render(20)
    ) == ["R"]


def test_deeply_nested():
    tree = vstack(
        hstack(text("title"), text("v1.0"), justify_content="between"),
        table(table_row(text(">"), text("item"), text(color(2, "ok")))),
        hstack(text("[q] quit"), text("[h] help"), wrap=True, spacing=2),
    )
    assert len(tree.render(60)) >= 3
