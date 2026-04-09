"""Tests for Cond component."""

from helpers import clean

from terminal import cond, scroll, text
from terminal.components.scroll import ScrollState


def test_true_renders_child():
    assert clean(cond(True, text("yes")).render(80)) == ["yes"]


def test_false_renders_empty():
    assert cond(False, text("no")).render(80) == []


def test_truthy_values():
    assert clean(cond(1, text("yes")).render(80)) == ["yes"]
    assert cond(0, text("no")).render(80) == []
    assert cond("", text("no")).render(80) == []
    assert clean(cond("x", text("yes")).render(80)) == ["yes"]


def test_flex_basis():
    assert cond(True, text("hello")).flex_basis == 5
    assert cond(False, text("hello")).flex_basis == 0


def test_grow_true():
    s = ScrollState()
    assert cond(True, scroll(text("a"), state=s)).grow


def test_grow_false_condition():
    s = ScrollState()
    assert not cond(False, scroll(text("a"), state=s)).grow


def test_grow_non_grower():
    assert not cond(True, text("a")).grow


def test_height_passed_to_child():
    s = ScrollState()
    c = cond(True, scroll(text("a"), text("b"), text("c"), state=s))
    assert clean(c.render(80, 2)) == ["a", "b"]
