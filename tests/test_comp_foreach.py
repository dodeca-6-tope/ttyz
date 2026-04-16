"""Tests for ForEach component."""

from conftest import SnapFn

from ttyz import foreach, text


def test_renders_items(snap: SnapFn):
    snap(foreach(["a", "b", "c"], lambda item, i: text(f"{i}:{item}")), 80)


def test_empty_list(snap: SnapFn):
    items: list[str] = []
    snap(foreach(items, lambda item, i: text(item)), 80)


def test_intrinsic_width(snap: SnapFn):
    """Foreach intrinsic width is max of children."""
    from ttyz import hstack

    snap(
        hstack(foreach(["hi", "hello"], lambda item, i: text(item)), text("|")),
        20,
    )


def test_children_get_outer_height(snap: SnapFn):
    """text() children ignore h, so render is the same with or without height."""
    items = ["a", "b", "c"]
    f = foreach(items, lambda item, i: text(item))
    snap(f, 80, name="foreach_height_no_h")
    snap(f, 80, 10, name="foreach_height_with_h")
