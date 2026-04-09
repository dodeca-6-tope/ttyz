"""Tests for VStack component."""

from helpers import clean

from terminal import scroll, text, vstack
from terminal.components.scroll import ScrollState


def test_stacks_children():
    assert clean(vstack(text("a"), text("b")).render(80)) == ["a", "b"]


def test_spacing():
    assert clean(vstack(text("a"), text("b"), spacing=1).render(80)) == ["a", "", "b"]


def test_empty():
    assert clean(vstack().render(80)) == []


def test_flex_basis():
    assert vstack(text("hello"), text("hi")).flex_basis == 5


# ── Height-constrained rendering ─────────────────────────────────────


def test_unconstrained_when_no_height():
    v = vstack(text("a"), text("b"), text("c"))
    assert clean(v.render(80)) == ["a", "b", "c"]
    assert clean(v.render(80, None)) == ["a", "b", "c"]


def test_constrained_no_growers_ignores_height():
    assert clean(vstack(text("a"), text("b")).render(80, 10)) == ["a", "b"]


def test_constrained_distributes_to_grower():
    s = ScrollState()
    v = vstack(text("header"), scroll(text("a"), text("b"), text("c"), state=s))
    assert clean(v.render(80, 4)) == ["header", "a", "b", "c"]


def test_constrained_multiple_fixed_children():
    s = ScrollState()
    v = vstack(
        text("top"), scroll(text("a"), text("b"), text("c"), state=s), text("bottom")
    )
    assert clean(v.render(80, 5)) == ["top", "a", "b", "c", "bottom"]


def test_constrained_with_spacing():
    s = ScrollState()
    v = vstack(
        text("top"),
        scroll(text("a"), text("b"), text("c"), text("d"), state=s),
        spacing=1,
    )
    assert clean(v.render(80, 5)) == ["top", "", "a", "b", "c"]


def test_constrained_two_growers():
    s1 = ScrollState()
    s2 = ScrollState()
    v = vstack(
        scroll(*[text(str(i)) for i in range(10)], state=s1),
        scroll(*[text(str(i + 10)) for i in range(10)], state=s2),
    )
    assert clean(v.render(80, 6)) == ["0", "1", "2", "10", "11", "12"]


def test_constrained_grower_gets_zero_when_fixed_fills():
    s = ScrollState()
    v = vstack(
        text("a"),
        text("b"),
        text("c"),
        scroll(text("x"), text("y"), state=s),
    )
    assert clean(v.render(80, 3)) == ["a", "b", "c"]


# ── flex_grow propagation ───────────────────────────────────────────


def test_grow_not_propagated_from_children():
    assert not vstack(text("a"), text("b", grow=1)).grow


def test_flex_grow_false_without_growers():
    assert not vstack(text("a"), text("b")).grow
