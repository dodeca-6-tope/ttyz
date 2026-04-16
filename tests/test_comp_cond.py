"""Tests for Cond component."""

from conftest import SnapFn

from ttyz import cond, scroll, text
from ttyz.components.scroll import ScrollState


def test_true_renders_child(snap: SnapFn):
    snap(cond(True, text("yes")), 80)


def test_false_renders_empty(snap: SnapFn):
    snap(cond(False, text("no")), 80)


def test_truthy_values(snap: SnapFn):
    snap(cond(1, text("yes")), 80, name="truthy_int")
    snap(cond(0, text("no")), 80, name="falsy_zero")
    snap(cond("", text("no")), 80, name="falsy_empty_str")
    snap(cond("x", text("yes")), 80, name="truthy_str")


def test_intrinsic_width(snap: SnapFn):
    """Cond delegates intrinsic width to active child."""
    from ttyz import hstack

    snap(hstack(cond(True, text("hello")), text("|")), 20, name="intrinsic_width_true")
    snap(
        hstack(cond(False, text("hello")), text("|")),
        20,
        name="intrinsic_width_false",
    )


def test_grow_true():
    s = ScrollState()
    assert cond(True, scroll(text("a"), state=s)).grow


def test_grow_false_condition():
    s = ScrollState()
    assert not cond(False, scroll(text("a"), state=s)).grow


def test_grow_non_grower():
    assert not cond(True, text("a")).grow


def test_height_passed_to_child(snap: SnapFn):
    s = ScrollState()
    c = cond(True, scroll(text("a"), text("b"), text("c"), state=s))
    snap(c, 80, 2)
